import { NextResponse } from 'next/server';
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

export async function GET() {
  try {
    const streamlinkPath = process.env.STREAMLINK_PATH || `${process.env.HOME}/.local/bin/streamlink`;
    
    // Get list of plugins from streamlink
    const { stdout } = await execAsync(`${streamlinkPath} --plugins`);
    
    // Parse the output to get plugin names
    const lines = stdout.split('\n');
    const plugins: Array<{
      name: string;
      domains: string[];
      requiresAuth: boolean;
      authFields: Array<{ name: string; type: string; label: string }>;
    }> = [];
    
    let inPluginList = false;
    for (const line of lines) {
      if (line.includes('Loaded plugins:') || line.includes('plugins:')) {
        inPluginList = true;
        continue;
      }
      if (inPluginList && line.trim()) {
        // Parse plugin names from the line
        const names = line.trim().split(/\s+/);
        for (const name of names) {
          if (name && name.length > 0 && !name.includes(':')) {
            const authInfo = AUTH_PLUGINS[name] || { requiresAuth: false, authFields: [] };
            plugins.push({
              name,
              domains: [],
              requiresAuth: authInfo.requiresAuth,
              authFields: authInfo.authFields,
            });
          }
        }
      }
    }
    
    // If no plugins found via parsing, try alternative method
    if (plugins.length === 0) {
      // Alternative: just list common plugins
      const commonPlugins = [
        'twitch', 'youtube', 'dailymotion', 'vimeo', 'facebook',
        '10play', 'bbciplayer', 'artetv', 'nhkworld', 'steam',
        'streamable', 'wistia', 'picarto', 'okru', 'periscope',
        'restream', 'ruv', 'scaleway', 'ssai', 'stripchat',
        'ustream', 'ustvnow', 'vimeo', 'vk', 'webtv', 'wix',
        'youtube', 'zattoo', 'zhihu'
      ];
      
      for (const name of commonPlugins) {
        const authInfo = AUTH_PLUGINS[name] || { requiresAuth: false, authFields: [] };
        plugins.push({
          name,
          domains: [],
          requiresAuth: authInfo.requiresAuth,
          authFields: authInfo.authFields,
        });
      }
    }
    
    return NextResponse.json({ plugins: plugins.sort((a, b) => a.name.localeCompare(b.name)) });
  } catch (error) {
    console.error('Error getting plugins:', error);
    return NextResponse.json({ error: 'Failed to get plugins', plugins: [] }, { status: 500 });
  }
}
