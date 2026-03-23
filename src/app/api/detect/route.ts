import { NextRequest, NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

// Auth requirements for known plugins
const AUTH_PLUGINS: Record<string, { requiresAuth: boolean; authFields: Array<{ name: string; type: string; label: string }> }> = {
  '10play': { requiresAuth: true, authFields: [
    { name: 'email', type: 'email', label: 'Email' },
    { name: 'password', type: 'password', label: 'Password' }
  ]},
  'twitch': { requiresAuth: false, authFields: [] },
  'youtube': { requiresAuth: false, authFields: [] },
  'vimeo': { requiresAuth: false, authFields: [] },
  'dailymotion': { requiresAuth: false, authFields: [] },
  'facebook': { requiresAuth: true, authFields: [
    { name: 'email', type: 'email', label: 'Email' },
    { name: 'password', type: 'password', label: 'Password' }
  ]},
};

export async function POST(request: NextRequest) {
  try {
    const { url } = await request.json();
    
    if (!url) {
      return NextResponse.json({ error: 'URL is required', plugin: null }, { status: 400 });
    }
    
    const streamlinkPath = process.env.STREAMLINK_PATH || 'streamlink';
    
    // Try to detect the plugin
    try {
      const { stdout, stderr } = await execAsync(`${streamlinkPath} --json "${url}" 2>&1`, {
        timeout: 30000,
      });
      
      // Try to parse JSON output
      try {
        const result = JSON.parse(stdout);
        
        if (result.plugin) {
          const authInfo = AUTH_PLUGINS[result.plugin] || { requiresAuth: false, authFields: [] };
          return NextResponse.json({
            plugin: {
              name: result.plugin,
              domains: [],
              requiresAuth: authInfo.requiresAuth,
              authFields: authInfo.authFields,
            },
            streams: Object.keys(result.streams || {}),
          });
        }
        
        return NextResponse.json({ plugin: null, error: 'No plugin detected in output' });
      } catch {
        // Not JSON, check output for plugin name
        const output = stdout + stderr;
        
        // Look for plugin name in output
        const pluginMatch = output.match(/plugin[:\s]+['"]?(\w+)['"]?/i);
        if (pluginMatch) {
          const pluginName = pluginMatch[1].toLowerCase();
          const authInfo = AUTH_PLUGINS[pluginName] || { requiresAuth: false, authFields: [] };
          return NextResponse.json({
            plugin: {
              name: pluginName,
              domains: [],
              requiresAuth: authInfo.requiresAuth,
              authFields: authInfo.authFields,
            },
          });
        }
        
        // No plugin found
        if (output.includes('No plugin can handle') || output.includes('error:')) {
          return NextResponse.json({ plugin: null, error: 'No plugin found for this URL' });
        }
        
        return NextResponse.json({ plugin: null, error: `Unexpected output: ${output.substring(0, 200)}` });
      }
    } catch (execError: unknown) {
      const error = execError as { stderr?: string; stdout?: string; message?: string };
      const output = (error.stdout || '') + (error.stderr || '');
      
      // Check for specific errors
      if (output.includes('No plugin can handle')) {
        return NextResponse.json({ plugin: null, error: 'No plugin found for this URL' });
      }
      if (output.includes('command not found') || output.includes('not found')) {
        return NextResponse.json({ plugin: null, error: 'Streamlink is not installed in the container' });
      }
      
      // Try to extract plugin from error output
      const pluginMatch = output.match(/plugin[:\s]+['"]?(\w+)['"]?/i);
      if (pluginMatch) {
        const pluginName = pluginMatch[1].toLowerCase();
        const authInfo = AUTH_PLUGINS[pluginName] || { requiresAuth: false, authFields: [] };
        return NextResponse.json({
          plugin: {
            name: pluginName,
            domains: [],
            requiresAuth: authInfo.requiresAuth,
            authFields: authInfo.authFields,
          },
        });
      }
      
      return NextResponse.json({ 
        plugin: null, 
        error: `Streamlink error: ${output.substring(0, 200) || error.message || 'Unknown error'}` 
      });
    }
  } catch (error) {
    console.error('Error detecting plugin:', error);
    return NextResponse.json({ error: 'Failed to detect plugin', plugin: null }, { status: 500 });
  }
}
