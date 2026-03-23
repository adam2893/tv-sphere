import { NextRequest, NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export async function POST(request: NextRequest) {
  try {
    const { url, quality = 'best', credentials = {} } = await request.json();
    
    if (!url) {
      return NextResponse.json({ error: 'URL is required', streams: [] }, { status: 400 });
    }
    
    const streamlinkPath = process.env.STREAMLINK_PATH || `${process.env.HOME}/.local/bin/streamlink`;
    
    // Build the command with credentials
    let cmd = `${streamlinkPath} --json --stream-url`;
    
    // Add credentials if provided
    for (const [key, value] of Object.entries(credentials)) {
      if (value) {
        cmd += ` --${key}="${value}"`;
      }
    }
    
    // Add URL and quality
    cmd += ` "${url}" "${quality}"`;
    
    console.log('Executing:', cmd.replace(/--[\w-]+password[\w-]*="[^"]*"/gi, '--password="***"'));
    
    try {
      const { stdout, stderr } = await execAsync(cmd, {
        timeout: 60000, // 60 second timeout
      });
      
      // Try to parse JSON output
      try {
        const result = JSON.parse(stdout);
        
        if (result.streams) {
          const streams = Object.entries(result.streams).map(([q, stream]: [string, unknown]) => {
            const streamObj = stream as { url?: string; type?: string };
            return {
              quality: q,
              url: streamObj.url || '',
              type: streamObj.type || 'unknown',
            };
          });
          
          return NextResponse.json({
            streams,
            plugin: result.plugin,
            url,
          });
        }
        
        // If just a URL was returned
        if (stdout.trim().startsWith('http')) {
          return NextResponse.json({
            streams: [{
              quality,
              url: stdout.trim(),
              type: 'hls',
            }],
            url,
          });
        }
      } catch {
        // Not JSON, check if it's a plain URL
        if (stdout.trim().startsWith('http')) {
          return NextResponse.json({
            streams: [{
              quality,
              url: stdout.trim(),
              type: 'hls',
            }],
            url,
          });
        }
      }
      
      return NextResponse.json({ streams: [], error: 'Could not parse stream output' });
      
    } catch (execError: unknown) {
      const error = execError as { stderr?: string; message?: string };
      const errorMsg = error.stderr || error.message || 'Unknown error';
      
      console.error('Streamlink error:', errorMsg);
      
      // Parse common errors
      if (errorMsg.includes('No plugin can handle')) {
        return NextResponse.json({ streams: [], error: 'No plugin can handle this URL' });
      }
      if (errorMsg.includes('No streams found')) {
        return NextResponse.json({ streams: [], error: 'No streams found on this page' });
      }
      if (errorMsg.includes('403') || errorMsg.includes('Forbidden')) {
        return NextResponse.json({ streams: [], error: 'Access denied - credentials may be required or invalid' });
      }
      if (errorMsg.includes('404') || errorMsg.includes('Not Found')) {
        return NextResponse.json({ streams: [], error: 'Stream not found' });
      }
      if (errorMsg.includes('geo') || errorMsg.includes('region')) {
        return NextResponse.json({ streams: [], error: 'Stream is geo-blocked' });
      }
      
      return NextResponse.json({ streams: [], error: errorMsg });
    }
  } catch (error) {
    console.error('Error resolving stream:', error);
    return NextResponse.json({ error: 'Failed to resolve stream', streams: [] }, { status: 500 });
  }
}
