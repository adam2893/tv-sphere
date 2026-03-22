import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/lib/db';

// GET - Generate M3U playlist
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const playlistId = searchParams.get('playlistId');
    const download = searchParams.get('download') === 'true';
    
    let channels: Array<{ id: string; name: string; url: string; logo: string | null; category: string | null }> = [];
    
    if (playlistId) {
      const playlist = await db.playlist.findUnique({
        where: { id: playlistId },
        include: { channels: true },
      });
      
      if (!playlist) {
        return NextResponse.json({ error: 'Playlist not found' }, { status: 404 });
      }
      
      channels = playlist.channels;
    } else {
      // Get all channels from all playlists
      channels = await db.channel.findMany({
        orderBy: { name: 'asc' },
      });
    }
    
    // Generate M3U content
    const lines: string[] = ['#EXTM3U'];
    
    for (const channel of channels) {
      lines.push('');
      lines.push(`#EXTINF:-1 tvg-name="${channel.name}" tvg-id="${channel.id}"${channel.logo ? ` tvg-logo="${channel.logo}"` : ''}${channel.category ? ` group-title="${channel.category}"` : ''},${channel.name}`);
      lines.push(channel.url);
    }
    
    const m3uContent = lines.join('\n');
    
    if (download) {
      return new NextResponse(m3uContent, {
        headers: {
          'Content-Type': 'audio/x-mpegurl',
          'Content-Disposition': 'attachment; filename="playlist.m3u"',
        },
      });
    }
    
    return NextResponse.json({ m3u: m3uContent, channelCount: channels.length });
  } catch (error) {
    console.error('Error generating M3U:', error);
    return NextResponse.json({ error: 'Failed to generate M3U' }, { status: 500 });
  }
}
