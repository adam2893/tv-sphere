import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/lib/db';

// GET - List all playlists
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const id = searchParams.get('id');
    
    if (id) {
      const playlist = await db.playlist.findUnique({
        where: { id },
        include: { channels: true },
      });
      
      if (!playlist) {
        return NextResponse.json({ error: 'Playlist not found' }, { status: 404 });
      }
      
      return NextResponse.json({ playlist });
    }
    
    const playlists = await db.playlist.findMany({
      include: { _count: { select: { channels: true } } },
      orderBy: { createdAt: 'desc' },
    });
    
    return NextResponse.json({ playlists });
  } catch (error) {
    console.error('Error fetching playlists:', error);
    return NextResponse.json({ error: 'Failed to fetch playlists' }, { status: 500 });
  }
}

// POST - Create playlist
export async function POST(request: NextRequest) {
  try {
    const { name, description, channels } = await request.json();
    
    if (!name) {
      return NextResponse.json({ error: 'Playlist name is required' }, { status: 400 });
    }
    
    const playlist = await db.playlist.create({
      data: {
        name,
        description,
        channels: channels ? {
          create: channels.map((ch: { name: string; url: string; logo?: string; category?: string }) => ({
            name: ch.name,
            url: ch.url,
            logo: ch.logo,
            category: ch.category,
          })),
        } : undefined,
      },
      include: { channels: true },
    });
    
    return NextResponse.json({ playlist });
  } catch (error) {
    console.error('Error creating playlist:', error);
    return NextResponse.json({ error: 'Failed to create playlist' }, { status: 500 });
  }
}

// PUT - Update playlist
export async function PUT(request: NextRequest) {
  try {
    const { id, name, description, channels } = await request.json();
    
    if (!id) {
      return NextResponse.json({ error: 'Playlist ID is required' }, { status: 400 });
    }
    
    // Delete existing channels and recreate
    if (channels) {
      await db.channel.deleteMany({
        where: { playlistId: id },
      });
    }
    
    const playlist = await db.playlist.update({
      where: { id },
      data: {
        name,
        description,
        channels: channels ? {
          create: channels.map((ch: { name: string; url: string; logo?: string; category?: string }) => ({
            name: ch.name,
            url: ch.url,
            logo: ch.logo,
            category: ch.category,
          })),
        } : undefined,
      },
      include: { channels: true },
    });
    
    return NextResponse.json({ playlist });
  } catch (error) {
    console.error('Error updating playlist:', error);
    return NextResponse.json({ error: 'Failed to update playlist' }, { status: 500 });
  }
}

// DELETE - Delete playlist
export async function DELETE(request: NextRequest) {
  try {
    const { id } = await request.json();
    
    if (!id) {
      return NextResponse.json({ error: 'Playlist ID is required' }, { status: 400 });
    }
    
    await db.playlist.delete({
      where: { id },
    });
    
    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Error deleting playlist:', error);
    return NextResponse.json({ error: 'Failed to delete playlist' }, { status: 500 });
  }
}
