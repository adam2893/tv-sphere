import { NextRequest, NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

// Auth requirements for known plugins
const AUTH_PLUGINS: Record<string, { requiresAuth: boolean; authFields: Array<{ name: string; type: string; label: string }> }> = {
  'twitch': { requiresAuth: false, authFields: [] },
  'youtube': { requiresAuth: false, authFields: [] },
  '10play': { requiresAuth: true, authFields: [
    { name: 'email', type: 'email', label: 'Email' },
    { name: 'password', type: 'password', label: 'Password' }
  ]},
  'bbciplayer': { requiresAuth: false, authFields: [] },
  'artetv': { requiresAuth: false, authFields: [] },
  'dailymotion': { requiresAuth: false, authFields: [] },
  'facebook': { requiresAuth: true, authFields: [
    { name: 'email', type: 'email', label: 'Email' },
    { name: 'password', type: 'password', label: 'Password' }
  ]},
  'nhkworld': { requiresAuth: false, authFields: [] },
  'vimeo': { requiresAuth: false, authFields: [] },
  'steam': { requiresAuth: false, authFields: [] },
  'streamable': { requiresAuth: false, authFields: [] },
};

export async function POST(request: NextRequest) {
  try {
    const { url } = await request.json();
    
    if (!url) {
      return NextResponse.json({ error: 'URL is required', plugin: null }, { status: 400 });
    }
    
    const streamlinkPath = process.env.STREAMLINK_PATH || `${process.env.HOME}/.local/bin/streamlink`;
    
    // Try to detect the plugin
    try {
      const { stdout, stderr } = await execAsync(`${streamlinkPath} --json "${url}"`, {
        timeout: 30000,
      });
      
      // Parse the JSON output
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
      
      return NextResponse.json({ plugin: null, error: 'No plugin detected' });
    } catch (execError: unknown) {
      const error = execError as { stderr?: string; message?: string };
      // Check if stderr contains plugin info
      const stderrText = error.stderr || error.message || '';
      
      // Try to extract plugin name from error
      const pluginMatch = stderrText.match(/plugin[:\s]+(\w+)/i);
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
      if (stderrText.includes('No plugin can handle')) {
        return NextResponse.json({ plugin: null, error: 'No plugin found for this URL' });
      }
      
      return NextResponse.json({ plugin: null, error: stderrText || 'Failed to detect plugin' });
    }
  } catch (error) {
    console.error('Error detecting plugin:', error);
    return NextResponse.json({ error: 'Failed to detect plugin', plugin: null }, { status: 500 });
  }
}
