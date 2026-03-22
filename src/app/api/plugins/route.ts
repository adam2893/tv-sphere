import { NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

// Known plugins that require authentication
const AUTH_PLUGINS: Record<string, { requiresAuth: boolean; authFields: Array<{ name: string; type: string; label: string }> }> = {
  '10play': { 
    requiresAuth: true, 
    authFields: [
      { name: 'email', type: 'email', label: 'Email' },
      { name: 'password', type: 'password', label: 'Password' }
    ]
  },
  'bbciplayer': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'facebook': { 
    requiresAuth: true, 
    authFields: [
      { name: 'email', type: 'email', label: 'Email' },
      { name: 'password', type: 'password', label: 'Password' }
    ]
  },
  'linkedin': { 
    requiresAuth: true, 
    authFields: [
      { name: 'email', type: 'email', label: 'Email' },
      { name: 'password', type: 'password', label: 'Password' }
    ]
  },
  'nbcnews': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'nbcports': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'nebula': { 
    requiresAuth: true, 
    authFields: [
      { name: 'email', type: 'email', label: 'Email' },
      { name: 'password', type: 'password', label: 'Password' }
    ]
  },
  'nfl': { 
    requiresAuth: true, 
    authFields: [
      { name: 'email', type: 'email', label: 'Email' },
      { name: 'password', type: 'password', label: 'Password' }
    ]
  },
  'nrl': { 
    requiresAuth: true, 
    authFields: [
      { name: 'email', type: 'email', label: 'Email' },
      { name: 'password', type: 'password', label: 'Password' }
    ]
  },
  'steam': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'twitch': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'youtube': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'vimeo': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'dailymotion': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'periscope': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'picarto': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'piczel': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'okru': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'vk': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'webtv': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'ustream': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'nhkworld': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'artetv': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'bfmtv': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'bfmbusiness': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'lcp': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'neteasemusic': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'openrectv': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'qqmusic': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'radionet': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'rtbf': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'rte': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'rvr': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'showroom': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'sportschau': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'spotify': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'sr': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'srmediathek': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'swrmediathek': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'teamliquid': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'telefe': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'tf1': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'theplatform': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'tldr': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'tv360': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'tv4play': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'tv8': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'tvibo': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'tvp': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'tvplayer': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'tvrby': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'tvrplus': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'tvtoya': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'ustvnow': { 
    requiresAuth: true, 
    authFields: [
      { name: 'email', type: 'email', label: 'Email' },
      { name: 'password', type: 'password', label: 'Password' }
    ]
  },
  'viutv': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'vkplay': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'vlive': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'vrtbe': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'vtmbe': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'washingtonpost': { 
    requiresAuth: true, 
    authFields: [
      { name: 'email', type: 'email', label: 'Email' },
      { name: 'password', type: 'password', label: 'Password' }
    ]
  },
  'webcampics': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'welt': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'wwe': { 
    requiresAuth: true, 
    authFields: [
      { name: 'email', type: 'email', label: 'Email' },
      { name: 'password', type: 'password', label: 'Password' }
    ]
  },
  'youtube': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'zattoo': { 
    requiresAuth: true, 
    authFields: [
      { name: 'email', type: 'email', label: 'Email' },
      { name: 'password', type: 'password', label: 'Password' }
    ]
  },
  'zdf_mediathek': { 
    requiresAuth: false, 
    authFields: [] 
  },
  'zhihu': { 
    requiresAuth: false, 
    authFields: [] 
  },
};

// Common streaming site domains
const PLUGIN_DOMAINS: Record<string, string[]> = {
  twitch: ['twitch.tv'],
  youtube: ['youtube.com', 'youtu.be'],
  vimeo: ['vimeo.com'],
  dailymotion: ['dailymotion.com'],
  facebook: ['facebook.com'],
  twitter: ['twitter.com', 'x.com'],
  periscope: ['periscope.tv', 'pscp.tv'],
  '10play': ['10play.com.au'],
  bbciplayer: ['bbc.co.uk', 'bbc.com'],
  artetv: ['arte.tv'],
  nhkworld: ['nhk.or.jp', 'nhkworld.jp'],
  nbcnews: ['nbcnews.com'],
  nfl: ['nfl.com'],
  nrl: ['nrl.com'],
  wwe: ['wwe.com'],
  zattoo: ['zattoo.com'],
  vrtbe: ['vrt.be'],
  viutv: ['viu.tv'],
  vk: ['vk.com'],
  okru: ['ok.ru'],
  picarto: ['picarto.tv'],
  piczel: ['piczel.tv'],
  ustream: ['ustream.tv'],
  tvp: ['tvp.pl'],
  tf1: ['tf1.fr'],
  bfmtv: ['bfmtv.com'],
  rtbf: ['rtbf.be'],
  rte: ['rte.ie'],
  tv4play: ['tv4play.se'],
  spotify: ['spotify.com'],
  neteasemusic: ['music.163.com'],
  qqmusic: ['y.qq.com'],
};

export async function GET() {
  try {
    const streamlinkPath = process.env.STREAMLINK_PATH || 'streamlink';
    
    // Get list of plugins from streamlink
    let pluginNames: string[] = [];
    
    try {
      const { stdout } = await execAsync(`${streamlinkPath} --plugins 2>&1`);
      
      // Parse the output to get plugin names
      const lines = stdout.split('\n');
      let inPluginList = false;
      
      for (const line of lines) {
        if (line.includes('Loaded plugins:') || line.includes('plugins:')) {
          inPluginList = true;
          continue;
        }
        if (inPluginList && line.trim()) {
          const names = line.trim().split(/\s+/);
          pluginNames.push(...names.filter(n => n && !n.includes(':') && n.length > 1));
        }
      }
    } catch {
      // If streamlink command fails, use fallback list
      pluginNames = Object.keys(AUTH_PLUGINS);
    }
    
    // If no plugins found, use fallback
    if (pluginNames.length === 0) {
      pluginNames = Object.keys(AUTH_PLUGINS);
    }
    
    // Build plugin list
    const plugins = pluginNames.map(name => {
      const authInfo = AUTH_PLUGINS[name] || { requiresAuth: false, authFields: [] };
      const domains = PLUGIN_DOMAINS[name] || [];
      
      return {
        name,
        domains,
        requiresAuth: authInfo.requiresAuth,
        authFields: authInfo.authFields,
      };
    }).sort((a, b) => a.name.localeCompare(b.name));
    
    return NextResponse.json({ plugins });
  } catch (error) {
    console.error('Error getting plugins:', error);
    
    // Fallback to static list
    const plugins = Object.entries(AUTH_PLUGINS).map(([name, authInfo]) => ({
      name,
      domains: PLUGIN_DOMAINS[name] || [],
      requiresAuth: authInfo.requiresAuth,
      authFields: authInfo.authFields,
    })).sort((a, b) => a.name.localeCompare(b.name));
    
    return NextResponse.json({ plugins });
  }
}
