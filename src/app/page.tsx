'use client';

import { useState, useCallback, useEffect } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { 
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { 
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { 
  Play, 
  Search, 
  Copy, 
  ExternalLink, 
  Loader2, 
  Key, 
  List, 
  Download,
  Trash2,
  Plus,
  Save,
  Video,
  CheckCircle,
  XCircle,
  RefreshCw,
} from 'lucide-react';
import { toast } from 'sonner';

interface Plugin {
  name: string;
  domains: string[];
  requiresAuth: boolean;
  authFields: Array<{ name: string; type: string; label: string }>;
}

interface Stream {
  quality: string;
  url: string;
  type: string;
}

interface Credential {
  id: string;
  plugin: string;
  name: string;
  email: string | null;
  hasPassword: boolean;
  hasToken: boolean;
  createdAt: string;
}

interface Playlist {
  id: string;
  name: string;
  description: string | null;
  channels?: Array<{ id: string; name: string; url: string; logo?: string; category?: string }>;
  _count?: { channels: number };
}

export default function TVSpherePage() {
  // Stream tab state
  const [url, setUrl] = useState('');
  const [detectedPlugin, setDetectedPlugin] = useState<Plugin | null>(null);
  const [streams, setStreams] = useState<Stream[]>([]);
  const [loading, setLoading] = useState(false);
  const [detecting, setDetecting] = useState(false);
  const [credentials, setCredentials] = useState<Record<string, string>>({});
  
  // Plugins tab state
  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [loadingPlugins, setLoadingPlugins] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  
  // Playlists tab state
  const [playlists, setPlaylists] = useState<Playlist[]>([]);
  const [loadingPlaylists, setLoadingPlaylists] = useState(false);
  const [newPlaylistDialog, setNewPlaylistDialog] = useState(false);
  const [newPlaylistName, setNewPlaylistName] = useState('');
  const [newPlaylistDesc, setNewPlaylistDesc] = useState('');
  
  // Credentials tab state
  const [savedCredentials, setSavedCredentials] = useState<Credential[]>([]);
  const [loadingCredentials, setLoadingCredentials] = useState(false);
  const [newCredDialog, setNewCredDialog] = useState(false);
  const [newCredPlugin, setNewCredPlugin] = useState('');
  const [newCredName, setNewCredName] = useState('');
  const [newCredEmail, setNewCredEmail] = useState('');
  const [newCredPassword, setNewCredPassword] = useState('');
  const [savingCred, setSavingCred] = useState(false);

  // Load plugins on mount
  useEffect(() => {
    loadPlugins();
    loadPlaylists();
    loadCredentials();
  }, []);

  // Detect plugin from URL
  const handleDetect = useCallback(async () => {
    if (!url) {
      toast.error('Please enter a URL');
      return;
    }

    setDetecting(true);
    setDetectedPlugin(null);
    setStreams([]);

    try {
      const response = await fetch('/api/detect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });

      const data = await response.json();

      if (data.plugin) {
        setDetectedPlugin(data.plugin);
        toast.success(`Detected plugin: ${data.plugin.name}`);
      } else {
        toast.error(data.error || 'No plugin found for this URL');
      }
    } catch {
      toast.error('Failed to detect plugin');
    } finally {
      setDetecting(false);
    }
  }, [url]);

  // Resolve stream
  const handleResolve = useCallback(async () => {
    if (!url) {
      toast.error('Please enter a URL');
      return;
    }

    setLoading(true);
    setStreams([]);

    try {
      const response = await fetch('/api/resolve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, credentials }),
      });

      const data = await response.json();

      if (data.streams && data.streams.length > 0) {
        setStreams(data.streams);
        toast.success(`Found ${data.streams.length} stream(s)`);
      } else {
        toast.error(data.error || 'No streams found');
      }
    } catch {
      toast.error('Failed to resolve stream');
    } finally {
      setLoading(false);
    }
  }, [url, credentials]);

  // Load plugins
  const loadPlugins = useCallback(async () => {
    setLoadingPlugins(true);
    try {
      const response = await fetch('/api/plugins');
      const data = await response.json();
      setPlugins(data.plugins || []);
    } catch {
      toast.error('Failed to load plugins');
    } finally {
      setLoadingPlugins(false);
    }
  }, []);

  // Load playlists
  const loadPlaylists = useCallback(async () => {
    setLoadingPlaylists(true);
    try {
      const response = await fetch('/api/playlists');
      const data = await response.json();
      setPlaylists(data.playlists || []);
    } catch {
      toast.error('Failed to load playlists');
    } finally {
      setLoadingPlaylists(false);
    }
  }, []);

  // Load credentials
  const loadCredentials = useCallback(async () => {
    setLoadingCredentials(true);
    try {
      const response = await fetch('/api/credentials');
      const data = await response.json();
      setSavedCredentials(data.credentials || []);
    } catch {
      toast.error('Failed to load credentials');
    } finally {
      setLoadingCredentials(false);
    }
  }, []);

  // Create playlist
  const createPlaylist = useCallback(async () => {
    if (!newPlaylistName.trim()) {
      toast.error('Please enter a playlist name');
      return;
    }

    try {
      const response = await fetch('/api/playlists', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newPlaylistName, description: newPlaylistDesc }),
      });

      if (response.ok) {
        toast.success('Playlist created');
        setNewPlaylistDialog(false);
        setNewPlaylistName('');
        setNewPlaylistDesc('');
        loadPlaylists();
      } else {
        toast.error('Failed to create playlist');
      }
    } catch {
      toast.error('Failed to create playlist');
    }
  }, [newPlaylistName, newPlaylistDesc, loadPlaylists]);

  // Delete playlist
  const deletePlaylist = useCallback(async (id: string) => {
    if (!confirm('Delete this playlist?')) return;
    
    try {
      const response = await fetch('/api/playlists', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id }),
      });

      if (response.ok) {
        toast.success('Playlist deleted');
        loadPlaylists();
      } else {
        toast.error('Failed to delete playlist');
      }
    } catch {
      toast.error('Failed to delete playlist');
    }
  }, [loadPlaylists]);

  // Save credentials
  const saveCredentials = useCallback(async () => {
    if (!newCredPlugin.trim()) {
      toast.error('Please enter a plugin name');
      return;
    }

    setSavingCred(true);
    try {
      const response = await fetch('/api/credentials', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          plugin: newCredPlugin,
          name: newCredName || newCredPlugin,
          email: newCredEmail,
          password: newCredPassword,
        }),
      });

      if (response.ok) {
        toast.success('Credentials saved');
        setNewCredDialog(false);
        setNewCredPlugin('');
        setNewCredName('');
        setNewCredEmail('');
        setNewCredPassword('');
        loadCredentials();
      } else {
        toast.error('Failed to save credentials');
      }
    } catch {
      toast.error('Failed to save credentials');
    } finally {
      setSavingCred(false);
    }
  }, [newCredPlugin, newCredName, newCredEmail, newCredPassword, loadCredentials]);

  // Delete credentials
  const deleteCredentials = useCallback(async (id: string) => {
    if (!confirm('Delete these credentials?')) return;
    
    try {
      const response = await fetch('/api/credentials', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id }),
      });

      if (response.ok) {
        toast.success('Credentials deleted');
        loadCredentials();
      } else {
        toast.error('Failed to delete credentials');
      }
    } catch {
      toast.error('Failed to delete credentials');
    }
  }, [loadCredentials]);

  // Copy to clipboard
  const copyToClipboard = useCallback((text: string) => {
    navigator.clipboard.writeText(text);
    toast.success('Copied to clipboard');
  }, []);

  // Open in player
  const openInPlayer = useCallback((streamUrl: string) => {
    window.open(streamUrl, '_blank');
  }, []);

  // Download M3U
  const downloadM3U = useCallback(async (playlistId?: string) => {
    const downloadUrl = playlistId 
      ? `/api/m3u?playlistId=${playlistId}&download=true`
      : '/api/m3u?download=true';
    window.open(downloadUrl, '_blank');
  }, []);

  // Use plugin (fill URL)
  const usePlugin = useCallback((pluginName: string) => {
    const placeholders: Record<string, string> = {
      twitch: 'https://www.twitch.tv/username',
      youtube: 'https://www.youtube.com/watch?v=VIDEO_ID',
      vimeo: 'https://vimeo.com/VIDEO_ID',
      dailymotion: 'https://www.dailymotion.com/video/VIDEO_ID',
      facebook: 'https://www.facebook.com/watch/live/?v=VIDEO_ID',
    };
    setUrl(placeholders[pluginName] || `https://example.com/${pluginName}`);
    toast.info(`Enter a ${pluginName} URL`);
  }, []);

  // Filter plugins by search
  const filteredPlugins = plugins.filter(p => 
    p.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 text-white">
      <div className="container mx-auto p-4 max-w-6xl">
        {/* Header */}
        <div className="text-center mb-8 pt-8">
          <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
            TV Sphere 3.0
          </h1>
          <p className="text-gray-400 mt-2">Streamlink-powered stream extraction and IPTV management</p>
        </div>

        <Tabs defaultValue="stream" className="space-y-6">
          <TabsList className="grid w-full grid-cols-4 bg-gray-800/50">
            <TabsTrigger value="stream" className="data-[state=active]:bg-blue-600">
              <Play className="w-4 h-4 mr-2" />
              Stream
            </TabsTrigger>
            <TabsTrigger value="plugins" className="data-[state=active]:bg-blue-600">
              <Search className="w-4 h-4 mr-2" />
              Plugins ({plugins.length})
            </TabsTrigger>
            <TabsTrigger value="playlists" className="data-[state=active]:bg-blue-600">
              <List className="w-4 h-4 mr-2" />
              Playlists
            </TabsTrigger>
            <TabsTrigger value="credentials" className="data-[state=active]:bg-blue-600">
              <Key className="w-4 h-4 mr-2" />
              Credentials
            </TabsTrigger>
          </TabsList>

          {/* Stream Tab */}
          <TabsContent value="stream" className="space-y-4">
            <Card className="bg-gray-800/50 border-gray-700">
              <CardHeader>
                <CardTitle className="text-white">Extract Stream</CardTitle>
                <CardDescription className="text-gray-400">
                  Enter a streaming URL and we&apos;ll detect the plugin and extract the stream
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex gap-2">
                  <Input
                    placeholder="https://www.twitch.tv/username or any stream URL..."
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    className="bg-gray-700 border-gray-600 text-white placeholder-gray-400"
                    onKeyDown={(e) => e.key === 'Enter' && handleDetect()}
                  />
                  <Button onClick={handleDetect} disabled={detecting} variant="secondary">
                    {detecting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                    Detect
                  </Button>
                </div>

                {/* Detected Plugin */}
                {detectedPlugin && (
                  <div className="bg-gray-700/50 rounded-lg p-4 space-y-3">
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className="border-blue-500 text-blue-400">
                        {detectedPlugin.name}
                      </Badge>
                      {detectedPlugin.requiresAuth && (
                        <Badge variant="outline" className="border-yellow-500 text-yellow-400">
                          <Key className="w-3 h-3 mr-1" />
                          Auth Required
                        </Badge>
                      )}
                    </div>

                    {/* Auth Fields */}
                    {detectedPlugin.requiresAuth && detectedPlugin.authFields.length > 0 && (
                      <div className="grid gap-3">
                        {detectedPlugin.authFields.map((field) => (
                          <div key={field.name} className="grid gap-1">
                            <Label htmlFor={field.name} className="text-gray-300">
                              {field.label}
                            </Label>
                            <Input
                              id={field.name}
                              type={field.type}
                              placeholder={`Enter ${field.label.toLowerCase()}`}
                              value={credentials[field.name] || ''}
                              onChange={(e) => setCredentials({ ...credentials, [field.name]: e.target.value })}
                              className="bg-gray-600 border-gray-500 text-white"
                            />
                          </div>
                        ))}
                      </div>
                    )}

                    <Button onClick={handleResolve} disabled={loading} className="w-full bg-blue-600 hover:bg-blue-700">
                      {loading ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          Resolving...
                        </>
                      ) : (
                        <>
                          <Play className="w-4 h-4 mr-2" />
                          Resolve Stream
                        </>
                      )}
                    </Button>
                  </div>
                )}

                {/* Streams Results */}
                {streams.length > 0 && (
                  <div className="space-y-2">
                    <Label className="text-gray-300">Available Streams</Label>
                    <ScrollArea className="h-48 rounded-md border border-gray-700 bg-gray-700/30">
                      <div className="p-2 space-y-2">
                        {streams.map((stream, index) => (
                          <div key={index} className="bg-gray-700/50 rounded-lg p-3 flex items-center justify-between">
                            <div className="flex items-center gap-3">
                              <Badge variant="outline" className="border-green-500 text-green-400">
                                {stream.quality}
                              </Badge>
                              <span className="text-xs text-gray-400 truncate max-w-xs">
                                {stream.url.substring(0, 60)}...
                              </span>
                            </div>
                            <div className="flex gap-2">
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => copyToClipboard(stream.url)}
                                title="Copy URL"
                              >
                                <Copy className="w-4 h-4" />
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => openInPlayer(stream.url)}
                                title="Open in player"
                              >
                                <ExternalLink className="w-4 h-4" />
                              </Button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </ScrollArea>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Quick Tips */}
            <Card className="bg-gray-800/50 border-gray-700">
              <CardHeader>
                <CardTitle className="text-white text-sm">Quick Tips</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="text-sm text-gray-400 space-y-1">
                  <li>• Supported: Twitch, YouTube, Vimeo, Dailymotion, and {plugins.length}+ other sites</li>
                  <li>• Some sites require login credentials (10play, Facebook, etc.)</li>
                  <li>• Geo-blocked streams may need a VPN</li>
                  <li>• Click the stream URL to open in your default player</li>
                </ul>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Plugins Tab */}
          <TabsContent value="plugins" className="space-y-4">
            <Card className="bg-gray-800/50 border-gray-700">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-white">Available Plugins</CardTitle>
                    <CardDescription className="text-gray-400">
                      Click a plugin to use it, or search for specific sites
                    </CardDescription>
                  </div>
                  <Button variant="outline" size="sm" onClick={loadPlugins} disabled={loadingPlugins}>
                    <RefreshCw className={`w-4 h-4 mr-2 ${loadingPlugins ? 'animate-spin' : ''}`} />
                    Refresh
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className="mb-4">
                  <Input
                    placeholder="Search plugins..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="bg-gray-700 border-gray-600 text-white"
                  />
                </div>

                {loadingPlugins ? (
                  <div className="flex justify-center py-8">
                    <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
                  </div>
                ) : (
                  <ScrollArea className="h-96">
                    <div className="grid gap-2 pr-4">
                      {filteredPlugins.map((plugin) => (
                        <button
                          key={plugin.name}
                          onClick={() => usePlugin(plugin.name)}
                          className="bg-gray-700/50 hover:bg-gray-600/50 rounded-lg p-3 flex items-center justify-between text-left w-full transition-colors"
                        >
                          <div className="flex items-center gap-3">
                            <Video className="w-4 h-4 text-blue-400" />
                            <span className="font-medium text-white">{plugin.name}</span>
                            {plugin.requiresAuth && (
                              <Badge variant="outline" className="border-yellow-500 text-yellow-400 text-xs">
                                <Key className="w-3 h-3 mr-1" />
                                Auth
                              </Badge>
                            )}
                          </div>
                          {plugin.domains.length > 0 && (
                            <span className="text-xs text-gray-500">
                              {plugin.domains[0]}
                            </span>
                          )}
                        </button>
                      ))}
                    </div>
                  </ScrollArea>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Playlists Tab */}
          <TabsContent value="playlists" className="space-y-4">
            <Card className="bg-gray-800/50 border-gray-700">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-white">Playlists</CardTitle>
                    <CardDescription className="text-gray-400">
                      Manage your IPTV playlists and export as M3U
                    </CardDescription>
                  </div>
                  <Button 
                    className="bg-blue-600 hover:bg-blue-700"
                    onClick={() => setNewPlaylistDialog(true)}
                  >
                    <Plus className="w-4 h-4 mr-2" />
                    New Playlist
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                {loadingPlaylists ? (
                  <div className="flex justify-center py-8">
                    <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
                  </div>
                ) : playlists.length === 0 ? (
                  <div className="text-center py-8 text-gray-400">
                    <List className="w-12 h-12 mx-auto mb-2 opacity-50" />
                    <p>No playlists yet</p>
                    <p className="text-sm">Create a playlist to organize your streams</p>
                    <Button 
                      variant="outline" 
                      className="mt-4"
                      onClick={() => setNewPlaylistDialog(true)}
                    >
                      <Plus className="w-4 h-4 mr-2" />
                      Create Playlist
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {playlists.map((playlist) => (
                      <div
                        key={playlist.id}
                        className="bg-gray-700/50 rounded-lg p-4 flex items-center justify-between"
                      >
                        <div>
                          <h3 className="font-medium text-white">{playlist.name}</h3>
                          <p className="text-sm text-gray-400">
                            {playlist._count?.channels || 0} channels
                          </p>
                        </div>
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => downloadM3U(playlist.id)}
                            title="Download M3U"
                          >
                            <Download className="w-4 h-4" />
                          </Button>
                          <Button 
                            size="sm" 
                            variant="ghost" 
                            className="text-red-400"
                            onClick={() => deletePlaylist(playlist.id)}
                            title="Delete"
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                <Separator className="my-4 bg-gray-700" />

                <Button
                  variant="outline"
                  className="w-full border-gray-600 text-gray-300"
                  onClick={() => downloadM3U()}
                >
                  <Download className="w-4 h-4 mr-2" />
                  Export All as M3U
                </Button>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Credentials Tab */}
          <TabsContent value="credentials" className="space-y-4">
            <Card className="bg-gray-800/50 border-gray-700">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-white">Stored Credentials</CardTitle>
                    <CardDescription className="text-gray-400">
                      Manage login credentials for authenticated streaming services
                    </CardDescription>
                  </div>
                  <Button 
                    className="bg-blue-600 hover:bg-blue-700"
                    onClick={() => setNewCredDialog(true)}
                  >
                    <Plus className="w-4 h-4 mr-2" />
                    Add Credentials
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                {loadingCredentials ? (
                  <div className="flex justify-center py-8">
                    <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
                  </div>
                ) : savedCredentials.length === 0 ? (
                  <div className="text-center py-8 text-gray-400">
                    <Key className="w-12 h-12 mx-auto mb-2 opacity-50" />
                    <p>No saved credentials</p>
                    <p className="text-sm">Add credentials for services that require login</p>
                    <Button 
                      variant="outline" 
                      className="mt-4"
                      onClick={() => setNewCredDialog(true)}
                    >
                      <Plus className="w-4 h-4 mr-2" />
                      Add Credentials
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {savedCredentials.map((cred) => (
                      <div
                        key={cred.id}
                        className="bg-gray-700/50 rounded-lg p-4 flex items-center justify-between"
                      >
                        <div>
                          <h3 className="font-medium text-white">{cred.name}</h3>
                          <p className="text-sm text-gray-400">{cred.plugin}</p>
                        </div>
                        <div className="flex items-center gap-2">
                          {cred.email && (
                            <Badge variant="outline" className="border-green-500 text-green-400">
                              <CheckCircle className="w-3 h-3 mr-1" />
                              Email
                            </Badge>
                          )}
                          {cred.hasPassword && (
                            <Badge variant="outline" className="border-green-500 text-green-400">
                              <CheckCircle className="w-3 h-3 mr-1" />
                              Password
                            </Badge>
                          )}
                          <Button 
                            size="sm" 
                            variant="ghost" 
                            className="text-red-400"
                            onClick={() => deleteCredentials(cred.id)}
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* New Playlist Dialog */}
        <Dialog open={newPlaylistDialog} onOpenChange={setNewPlaylistDialog}>
          <DialogContent className="bg-gray-800 border-gray-700">
            <DialogHeader>
              <DialogTitle className="text-white">Create New Playlist</DialogTitle>
              <DialogDescription className="text-gray-400">
                Enter a name for your new playlist
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div>
                <Label className="text-gray-300">Name</Label>
                <Input
                  value={newPlaylistName}
                  onChange={(e) => setNewPlaylistName(e.target.value)}
                  placeholder="My Playlist"
                  className="bg-gray-700 border-gray-600 text-white"
                />
              </div>
              <div>
                <Label className="text-gray-300">Description (optional)</Label>
                <Input
                  value={newPlaylistDesc}
                  onChange={(e) => setNewPlaylistDesc(e.target.value)}
                  placeholder="Description"
                  className="bg-gray-700 border-gray-600 text-white"
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setNewPlaylistDialog(false)}>
                Cancel
              </Button>
              <Button className="bg-blue-600 hover:bg-blue-700" onClick={createPlaylist}>
                Create
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* New Credentials Dialog */}
        <Dialog open={newCredDialog} onOpenChange={setNewCredDialog}>
          <DialogContent className="bg-gray-800 border-gray-700">
            <DialogHeader>
              <DialogTitle className="text-white">Add Credentials</DialogTitle>
              <DialogDescription className="text-gray-400">
                Enter login credentials for a streaming service
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div>
                <Label className="text-gray-300">Plugin / Service</Label>
                {plugins.length > 0 ? (
                  <Select value={newCredPlugin} onValueChange={setNewCredPlugin}>
                    <SelectTrigger className="bg-gray-700 border-gray-600 text-white">
                      <SelectValue placeholder="Select a plugin" />
                    </SelectTrigger>
                    <SelectContent className="bg-gray-700 border-gray-600">
                      {plugins.filter(p => p.requiresAuth).map((p) => (
                        <SelectItem key={p.name} value={p.name} className="text-white hover:bg-gray-600">
                          {p.name}
                        </SelectItem>
                      ))}
                      <SelectItem value="other" className="text-white hover:bg-gray-600">
                        Other (enter manually)
                      </SelectItem>
                    </SelectContent>
                  </Select>
                ) : (
                  <Input
                    value={newCredPlugin}
                    onChange={(e) => setNewCredPlugin(e.target.value)}
                    placeholder="e.g., 10play"
                    className="bg-gray-700 border-gray-600 text-white"
                  />
                )}
              </div>
              <div>
                <Label className="text-gray-300">Display Name</Label>
                <Input
                  value={newCredName}
                  onChange={(e) => setNewCredName(e.target.value)}
                  placeholder="My 10Play Account"
                  className="bg-gray-700 border-gray-600 text-white"
                />
              </div>
              <div>
                <Label className="text-gray-300">Email / Username</Label>
                <Input
                  type="email"
                  value={newCredEmail}
                  onChange={(e) => setNewCredEmail(e.target.value)}
                  placeholder="your@email.com"
                  className="bg-gray-700 border-gray-600 text-white"
                />
              </div>
              <div>
                <Label className="text-gray-300">Password</Label>
                <Input
                  type="password"
                  value={newCredPassword}
                  onChange={(e) => setNewCredPassword(e.target.value)}
                  placeholder="••••••••"
                  className="bg-gray-700 border-gray-600 text-white"
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setNewCredDialog(false)}>
                Cancel
              </Button>
              <Button 
                className="bg-green-600 hover:bg-green-700" 
                onClick={saveCredentials}
                disabled={savingCred}
              >
                {savingCred ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    <Save className="w-4 h-4 mr-2" />
                    Save Credentials
                  </>
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Footer */}
        <footer className="text-center text-gray-500 text-sm mt-8 pb-4">
          <p>TV Sphere 3.0 - Powered by Streamlink</p>
          <p className="text-xs mt-1">For educational purposes only</p>
        </footer>
      </div>
    </div>
  );
}
