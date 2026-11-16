import React, {useEffect, useState} from 'react';
import {
  BackHandler, Image, Modal, Pressable, ScrollView, StyleSheet, Text, TextInput, View, useWindowDimensions,
} from 'react-native';
import {useKeplerAppStateManager} from '@amazon-devices/react-native-kepler';
import FileLink from 'tv-file-link-native';

// Vega OS gives apps only their own storage (/data), so the file manager works inside the
// TV File Link library. The browser transfer uses the same library.
const LIBRARY = '/data/library';

type Entry = {name: string; folder: boolean; size: number; modified?: number};
type Item = Entry & {path: string};
type Prompt = {action: 'mkdir' | 'rename' | 'delete' | 'rmtree'; path: string; title: string; detail?: string};
type Viewer = {kind: 'image' | 'text' | 'unsupported'; item: Item; text?: string};
type Clip = {item: Item; move: boolean};
type Stat = {size: number; items: number; modified: number};

const SORTS = ['Name', 'Date', 'Size'] as const;
const IMAGE = /\.(jpe?g|png|gif|webp|bmp)$/i;
const TEXT = /\.(txt|log|md|csv|json|xml|ini|conf|srt|vtt|html?|sh|properties|m3u)$/i;
const MEDIA = /\.(mp4|m4v|mkv|webm|3gp|mov|ts|avi|mp3|m4a|aac|wav|ogg|oga|flac|opus)$/i;

const color = {
  background: '#0e131e', panel: '#171f2e', row: '#243044', border: '#303a4c',
  ink: '#f5f4f0', muted: '#aebacd', gold: '#f4d68c', focus: '#ffe7aa', live: '#a7dfc2',
};

function call<T>(action: string, path = '', name = ''): T {
  const result = JSON.parse(FileLink.operate(LIBRARY, action, path, name));
  if (result.error) throw Error(result.error);
  return result.value as T;
}

function size(bytes: number) {
  const units = ['B', 'KB', 'MB', 'GB'];
  let value = bytes, unit = 0;
  while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit++; }
  return (unit ? value.toFixed(value < 10 ? 1 : 0) : value) + ' ' + units[unit];
}

function date(seconds?: number) {
  return seconds ? new Date(seconds * 1000).toLocaleString() : '';
}

function sorted(list: Entry[], sort: number) {
  return [...list].sort((a, b) => {
    if (a.folder !== b.folder) return a.folder ? -1 : 1;
    const byName = a.name.localeCompare(b.name, undefined, {sensitivity: 'base'});
    if (sort === 1) return (b.modified || 0) - (a.modified || 0) || byName;
    if (sort === 2 && !a.folder) return b.size - a.size || byName;
    return byName;
  });
}

function Action({title, run, disabled, preferred, full, primary, kind, description, subtitle}: {
  title: string; run: () => void; disabled?: boolean; preferred?: boolean; full?: boolean;
  primary?: boolean; kind?: 'folder' | 'file'; description?: string; subtitle?: string;
}) {
  const [focused, setFocused] = useState(false);
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={description || title}
      disabled={disabled} isTVSelectable={!disabled} hasTVPreferredFocus={preferred} onPress={run}
      onFocus={() => setFocused(true)} onBlur={() => setFocused(false)}
      style={[s.action, full && s.grow, primary && s.primary, disabled && s.disabled, focused && s.focused]}>
      {kind && <View style={[s.entryMark, kind === 'folder' ? s.folderMark : s.fileMark,
        focused && (kind === 'folder' ? s.focusedFolder : s.focusedFile)]} />}
      <View style={s.labelBox}>
        <Text numberOfLines={1} style={[s.actionText, (primary || focused) && s.focusedText]}>{title}</Text>
        {!!subtitle && <Text numberOfLines={1} style={[s.subText, focused && s.focusedText]}>{subtitle}</Text>}
      </View>
    </Pressable>
  );
}

export default function App() {
  const appState = useKeplerAppStateManager();
  const {width, height} = useWindowDimensions();
  const compact = height < 500;
  const [folder, setFolder] = useState('');
  const [entries, setEntries] = useState<Entry[]>([]);
  const [session, setSession] = useState('');
  const [message, setMessage] = useState('');
  const [item, setItem] = useState<Item | null>(null);
  const [prompt, setPrompt] = useState<Prompt | null>(null);
  const [name, setName] = useState('');
  const [formError, setFormError] = useState('');
  const [sort, setSort] = useState(0);
  const [clip, setClip] = useState<Clip | null>(null);
  const [viewer, setViewer] = useState<Viewer | null>(null);
  const [info, setInfo] = useState<{item: Item; stat?: Stat; error?: string} | null>(null);

  function refresh(target = folder) {
    try {
      setEntries(call<Entry[]>('list', target));
      setFolder(target);
      setMessage('');
    } catch (error) {
      setMessage((error as Error).message);
    }
  }

  function goUp() { refresh(folder.split('/').slice(0, -1).join('/')); }

  function stop() {
    try {
      call('stop');
      setSession('');
    } catch (error) {
      setMessage((error as Error).message);
    }
  }

  function toggle() {
    if (session) {
      refresh();
      stop();
      return;
    }
    try {
      setSession(call<string>('start'));
      setMessage('');
    } catch (error) {
      setMessage((error as Error).message);
    }
  }

  useEffect(() => {
    refresh('');
    const subscription = appState.addEventListener('change', state => {
      if (state === 'background') stop();
    });
    return () => {
      subscription.remove();
      call('stop');
    };
  }, []);

  // While a transfer is active, show browser uploads without pressing Refresh.
  useEffect(() => {
    if (!session) return;
    const timer = setInterval(() => {
      try {
        const next = call<Entry[]>('list', folder);
        setEntries(prev => JSON.stringify(prev) === JSON.stringify(next) ? prev : next);
      } catch {}
    }, 3000);
    return () => clearInterval(timer);
  }, [session, folder]);

  useEffect(() => {
    const subscription = BackHandler.addEventListener('hardwareBackPress', () => {
      if (viewer) { setViewer(null); return true; }
      if (!folder) return false;
      goUp();
      return true;
    });
    return () => subscription.remove();
  }, [folder, viewer]);

  function openPrompt(next: Prompt, initial = '') {
    setItem(null);
    setName(initial);
    setFormError('');
    setPrompt(next);
  }

  function submit() {
    if (!prompt) return;
    try {
      call(prompt.action, prompt.path, prompt.action === 'delete' || prompt.action === 'rmtree' ? '' : name.trim());
      if (clip && (prompt.action === 'delete' || prompt.action === 'rmtree') && clip.item.path === prompt.path) setClip(null);
      setPrompt(null);
      refresh();
    } catch (error) {
      setFormError((error as Error).message);
    }
  }

  function open(target: Item) {
    setItem(null);
    if (target.folder) { refresh(target.path); return; }
    if (IMAGE.test(target.name)) { setViewer({kind: 'image', item: target}); return; }
    if (TEXT.test(target.name)) {
      try {
        setViewer({kind: 'text', item: target, text: call<string>('read', target.path) || '(This file is empty.)'});
      } catch (error) {
        setMessage((error as Error).message);
      }
      return;
    }
    setViewer({kind: 'unsupported', item: target});
  }

  function askDelete(target: Item) {
    if (!target.folder) {
      openPrompt({action: 'delete', path: target.path, title: 'Delete ' + target.name + '?', detail: 'This cannot be undone.'});
      return;
    }
    let count = 0;
    try { count = call<Stat>('stat', target.path).items; } catch {}
    openPrompt(count === 0
      ? {action: 'delete', path: target.path, title: 'Delete folder ' + target.name + '?', detail: 'This folder is empty.'}
      : {action: 'rmtree', path: target.path, title: 'Delete folder ' + target.name + '?',
         detail: 'The folder and the ' + count + (count === 1 ? ' item' : ' items') + ' inside it will be deleted. This cannot be undone.'});
  }

  function paste() {
    if (!clip) return;
    try {
      const made = call<string>(clip.move ? 'move' : 'copy', clip.item.path, folder);
      setMessage((clip.move ? 'Moved ' : 'Copied ') + clip.item.name + (made !== clip.item.name ? ' as ' + made : '') + '.');
      if (clip.move) setClip(null);
      setEntries(call<Entry[]>('list', folder));
    } catch (error) {
      setMessage((error as Error).message);
    }
  }

  function details(target: Item) {
    setItem(null);
    try { setInfo({item: target, stat: call<Stat>('stat', target.path)}); }
    catch (error) { setInfo({item: target, error: (error as Error).message}); }
  }

  const [address, code] = session.split(' ');
  const list = sorted(entries, sort);
  return (
    <View style={[s.screen, compact && s.compact]}>
      <View style={s.header}>
        <Image source={require('./app-logo.png')} accessibilityLabel="TV File Link logo"
          style={[s.logo, compact && s.compactLogo]} />
        <Text style={[s.title, compact && s.compactTitle]}>TV File Link</Text>
      </View>
      <View style={s.layout}>
        <ScrollView style={[s.rail, {width: Math.min(440, Math.floor(width * .38))}]}
          contentContainerStyle={s.railContent} showsVerticalScrollIndicator={false}>
          <Text style={s.heading}>Wi-Fi Transfer</Text>
          {session ? (
            <>
              <Text accessibilityLiveRegion="polite" style={s.live}>Transfer active</Text>
              <Text style={s.copy}>On your phone or computer, open this address in a browser:</Text>
              <Text adjustsFontSizeToFit minimumFontScale={.7} numberOfLines={1} style={s.address}>{address}</Text>
              <Text style={s.copy}>6-digit code</Text>
              <Text style={s.code}>{code}</Text>
            </>
          ) : <Text style={s.copy}>Send files from a phone or computer on the same Wi-Fi network. They arrive in My files.</Text>}
          <Action title={session ? 'Stop transfer' : 'Start transfer'} run={toggle} primary preferred />
        </ScrollView>
        <View style={s.files}>
          <Text numberOfLines={1} ellipsizeMode="head" style={s.heading}>
            {folder ? 'My files / ' + folder : 'My files'}
          </Text>
          <View style={s.line}>
            <Action title="Up" run={goUp} disabled={!folder} />
            <Action title="New folder" run={() => openPrompt({action:'mkdir', path:folder, title:'New folder'})} />
            {clip && <Action title={(clip.move ? 'Move here: ' : 'Paste: ') + clip.item.name} run={paste} />}
            <Action title={'Sort: ' + SORTS[sort]} run={() => setSort((sort + 1) % SORTS.length)} />
            <Action title="Refresh" run={() => refresh()} />
          </View>
          <ScrollView style={s.list}>
            {list.length === 0 && <Text style={s.copy}>This folder is empty.</Text>}
            {list.map(entry => {
              const path = folder ? folder + '/' + entry.name : entry.name;
              const target = {...entry, path};
              const sub = (entry.folder ? 'Folder' : size(entry.size)) + (entry.modified ? '  ·  ' + date(entry.modified) : '');
              return (
                <View style={s.line} key={path}>
                  <Action full title={entry.name} subtitle={sub} kind={entry.folder ? 'folder' : 'file'}
                    description={(entry.folder ? 'Folder ' : 'File ') + entry.name} run={() => open(target)} />
                  <Action title="Options" description={'Options for ' + entry.name} run={() => setItem(target)} />
                </View>
              );
            })}
          </ScrollView>
          {!!message && <Text accessibilityLiveRegion="polite" style={s.error}>{message}</Text>}
        </View>
      </View>

      <Modal visible={!!item || !!prompt || !!info} transparent
        onRequestClose={() => {setItem(null); setPrompt(null); setInfo(null);}}>
        <View style={s.shade}><View style={s.dialog}>
          {item && (
            <>
              <Text numberOfLines={2} style={s.heading}>{item.name}</Text>
              <View style={s.wrap}>
                <Action preferred title="Open" run={() => open(item)} />
                <Action title="Copy" run={() => { setClip({item, move: false}); setItem(null);
                  setMessage('Ready to copy ' + item.name + '. Open the destination folder and select Paste.'); }} />
                <Action title="Move" run={() => { setClip({item, move: true}); setItem(null);
                  setMessage('Ready to move ' + item.name + '. Open the destination folder and select Move here.'); }} />
                <Action title="Rename" run={() => openPrompt({action:'rename', path:item.path, title:'Rename'}, item.name)} />
                <Action title="Delete" run={() => askDelete(item)} />
                <Action title="Details" run={() => details(item)} />
                <Action title="Close" run={() => setItem(null)} />
              </View>
              {!item.folder && <Text style={s.copy}>To download, start Wi-Fi Transfer and select Download in the browser.</Text>}
            </>
          )}
          {prompt && (
            <>
              <Text numberOfLines={2} style={s.heading}>{prompt.title}</Text>
              {!!prompt.detail && <Text style={s.copy}>{prompt.detail}</Text>}
              {(prompt.action === 'mkdir' || prompt.action === 'rename') && <TextInput style={s.input} value={name} onChangeText={setName}
                accessibilityLabel="File or folder name" autoFocus selectTextOnFocus onSubmitEditing={submit} />}
              {!!formError && <Text style={s.error}>{formError}</Text>}
              <View style={s.line}>
                <Action preferred={prompt.action === 'delete' || prompt.action === 'rmtree'} title="Cancel" run={() => setPrompt(null)} />
                <Action title={prompt.action === 'delete' || prompt.action === 'rmtree' ? 'Delete' : 'Save'} run={submit} />
              </View>
            </>
          )}
          {info && (
            <>
              <Text numberOfLines={2} style={s.heading}>{info.item.name}</Text>
              {info.error ? <Text style={s.error}>{info.error}</Text> : (
                <Text style={s.copy}>
                  {'Type: ' + (info.item.folder ? 'Folder' : (info.item.name.split('.').pop() || '').toUpperCase() + ' file') + '\n' +
                   'Size: ' + size(info.stat?.size || 0) + (info.item.folder ? ' in ' + (info.stat?.items || 0) + ' items' : '') + '\n' +
                   'Modified: ' + date(info.stat?.modified) + '\n' +
                   'Location: My files' + (folder ? ' / ' + folder : '')}
                </Text>
              )}
              <Action preferred title="OK" run={() => setInfo(null)} />
            </>
          )}
        </View></View>
      </Modal>

      <Modal visible={!!viewer} onRequestClose={() => setViewer(null)}>
        <View style={s.viewer}>
          {viewer?.kind === 'image' && (
            <Image source={{uri: 'file://' + LIBRARY + '/' + viewer.item.path}} resizeMode="contain"
              accessibilityLabel={'Image ' + viewer.item.name} style={s.fill} />
          )}
          {viewer?.kind === 'text' && (
            <ScrollView style={s.fill} contentContainerStyle={s.textPage}>
              <Text style={s.mono}>{viewer.text}</Text>
            </ScrollView>
          )}
          {viewer?.kind === 'unsupported' && (
            <Text style={s.copy}>
              {MEDIA.test(viewer.item.name)
                ? 'Video and audio playback is not available in the Vega edition yet. Start Wi-Fi Transfer to play it on another device.'
                : 'TV File Link cannot show this file type. Start Wi-Fi Transfer to download it to another device.'}
            </Text>
          )}
          <View style={s.viewerBar}>
            <Text style={s.copy}>{viewer?.item.name}</Text>
            <Action preferred title="Close" run={() => setViewer(null)} />
          </View>
        </View>
      </Modal>
    </View>
  );
}

const s = StyleSheet.create({
  screen: {flex:1, backgroundColor:color.background, paddingHorizontal:44, paddingVertical:28},
  compact: {paddingHorizontal:26, paddingVertical:15},
  header: {flexDirection:'row', alignItems:'center', marginBottom:16},
  logo: {width:72, height:72, borderRadius:14, borderColor:'#645637', borderWidth:1, marginRight:17},
  compactLogo: {width:52, height:52, borderRadius:11},
  title: {color:color.ink, fontSize:44, fontWeight:'700', letterSpacing:-1},
  compactTitle: {fontSize:34},
  layout: {flex:1, flexDirection:'row'},
  rail: {flexGrow:0, marginRight:18, borderRadius:17, backgroundColor:color.panel,
    borderWidth:1, borderColor:color.border},
  railContent: {padding:19, alignItems:'stretch'},
  files: {flex:1, padding:18, borderRadius:17, backgroundColor:color.panel,
    borderWidth:1, borderColor:color.border},
  heading: {color:color.ink, fontSize:28, fontWeight:'600', marginBottom:8},
  copy: {fontSize:17, marginBottom:8, color:color.muted},
  live: {color:color.live, fontWeight:'600', fontSize:15, marginBottom:10},
  address: {fontFamily:'monospace', fontSize:22, fontWeight:'700', color:'#ffffff', marginBottom:12},
  code: {fontFamily:'monospace', fontSize:46, fontWeight:'700', letterSpacing:8, color:color.gold,
    textAlign:'center', backgroundColor:color.background, borderColor:color.border,
    borderRadius:10, borderWidth:1, padding:7, marginBottom:12},
  line: {flexDirection:'row'},
  wrap: {flexDirection:'row', flexWrap:'wrap'},
  grow: {flex:1, justifyContent:'flex-start'},
  action: {flexDirection:'row', alignItems:'center', backgroundColor:color.row, minHeight:38,
    paddingHorizontal:13, paddingVertical:7, borderRadius:9, marginBottom:7, marginRight:8,
    justifyContent:'center', borderWidth:1, borderColor:'transparent'},
  labelBox: {flexShrink:1},
  actionText: {flexShrink:1, color:color.ink, fontSize:18, fontWeight:'600'},
  subText: {color:color.muted, fontSize:13},
  primary: {backgroundColor:color.gold, alignSelf:'flex-start'},
  disabled: {opacity:.45},
  focused: {backgroundColor:color.focus, borderColor:color.gold},
  focusedText: {color:color.background},
  entryMark: {width:17, height:14, marginRight:10, borderRadius:2},
  folderMark: {backgroundColor:color.gold, height:12},
  fileMark: {borderWidth:2, borderColor:color.muted, width:13, height:16},
  focusedFolder: {backgroundColor:color.background},
  focusedFile: {borderColor:color.background},
  list: {flex:1},
  error: {color:color.focus, fontSize:19, marginVertical:8},
  shade: {flex:1, justifyContent:'center', alignItems:'center', backgroundColor:'#000a'},
  dialog: {backgroundColor:color.panel, borderRadius:16, borderColor:color.border, borderWidth:1,
    padding:24, width:620, maxWidth:'90%'},
  input: {color:color.ink, backgroundColor:color.background, padding:10, marginVertical:10,
    fontSize:22, borderWidth:1, borderColor:color.muted},
  viewer: {flex:1, backgroundColor:'#000', justifyContent:'center', alignItems:'center'},
  fill: {width:'100%', height:'100%'},
  textPage: {padding:40, paddingBottom:120},
  mono: {fontFamily:'monospace', fontSize:18, color:color.ink},
  viewerBar: {position:'absolute', bottom:24, flexDirection:'row', alignItems:'center',
    backgroundColor:'#0e131ecc', borderRadius:10, paddingHorizontal:18, paddingTop:8},
});
