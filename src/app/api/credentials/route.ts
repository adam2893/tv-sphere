import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/lib/db';

// GET - List all credentials
export async function GET() {
  try {
    const credentials = await db.credential.findMany({
      orderBy: { plugin: 'asc' },
    });
    
    // Don't return actual passwords in list
    const safeCredentials = credentials.map(c => ({
      id: c.id,
      plugin: c.plugin,
      name: c.name,
      hasEmail: !!c.email,
      hasPassword: !!c.password,
      hasToken: !!c.token,
      createdAt: c.createdAt,
      updatedAt: c.updatedAt,
    }));
    
    return NextResponse.json({ credentials: safeCredentials });
  } catch (error) {
    console.error('Error fetching credentials:', error);
    return NextResponse.json({ error: 'Failed to fetch credentials' }, { status: 500 });
  }
}

// POST - Create or update credentials
export async function POST(request: NextRequest) {
  try {
    const { plugin, name, email, password, token, other } = await request.json();
    
    if (!plugin) {
      return NextResponse.json({ error: 'Plugin name is required' }, { status: 400 });
    }
    
    // Upsert the credential
    const credential = await db.credential.upsert({
      where: { plugin },
      create: {
        plugin,
        name: name || plugin,
        email,
        password,
        token,
        other,
      },
      update: {
        name: name || plugin,
        email,
        password,
        token,
        other,
      },
    });
    
    return NextResponse.json({ credential: { ...credential, password: '***' } });
  } catch (error) {
    console.error('Error saving credentials:', error);
    return NextResponse.json({ error: 'Failed to save credentials' }, { status: 500 });
  }
}

// DELETE - Delete credentials
export async function DELETE(request: NextRequest) {
  try {
    const { id } = await request.json();
    
    if (!id) {
      return NextResponse.json({ error: 'Credential ID is required' }, { status: 400 });
    }
    
    await db.credential.delete({
      where: { id },
    });
    
    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Error deleting credentials:', error);
    return NextResponse.json({ error: 'Failed to delete credentials' }, { status: 500 });
  }
}
