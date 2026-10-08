<script lang="ts">
  import { onMount } from 'svelte';
  import { fly } from 'svelte/transition';
  import { prefersReducedMotion } from 'svelte/motion';
  type Ending = 'white resigned' | 'black resigned' | 'draw claimed' | 'draw by agreement';
  type Position = { initial_fen: string; ending: Ending | null; fen: string; turn: string; pieces: Record<string, string>; legal_moves: string[]; moves: string[]; check: boolean; checked_king: string | null; last_move: string[]; captured: Record<string, string[]>; material_balance: number; result: string | null; termination: string | null; can_claim_draw: boolean; pgn: string };
  const glyphs: Record<string, string> = { K:'♔', Q:'♕', R:'♖', B:'♗', N:'♘', P:'♙', k:'♚', q:'♛', r:'♜', b:'♝', n:'♞', p:'♟' };
  const names: Record<string, string> = { k:'king', q:'queen', r:'rook', b:'bishop', n:'knight', p:'pawn' };
  let position = $state<Position | null>(null);
  let reviewed = $state<Position | null>(null);
  let reviewPly = $state(0);
  let selected = $state<string | null>(null);
  let flipped = $state(false);
  let busy = $state(false);
  let error = $state('');
  let promotion = $state<string[]>([]);
  let notation = $state('');
  let notice = $state('');
  let light = $state(false);
  let opponent = $state('local');
  let humanColor = $state('white');
  let difficulty = $state('medium');
  let engineAvailable = $state(false);
  let engineChecking = $state(true);
  let engineCheckInFlight = false;
  async function checkEngine() {
    if (engineCheckInFlight) return;
    engineCheckInFlight = true;
    try {
      const response = await fetch('/api/engine', {cache:'no-store', signal:AbortSignal.timeout(3000)});
      engineAvailable = response.ok && (await response.json()).available === true;
    } catch { engineAvailable = false; }
    finally { engineChecking = false; engineCheckInFlight = false; }
  }
  let importing = $state(false);
  let pgnText = $state('');
  let importError = $state('');
  type Analysis = {threats:{square:string;piece:string}[];cp:number; mate:number|null; lines:{cp:number;mate:number|null;uci:string[];san:string;explanation:string}[]};
  let analysis = $state<Analysis|null>(null);
  let analysing = $state(false);
  let report = $state<{ply:number;cp:number;loss:number;best:string}[]>([]);
  let reportRunning = $state(false);
  let reportGeneration = 0;
  let sound = $state(false);
  let audio: AudioContext | null = null;
  let arrow = $state<string[]>([]);
  let drag = $state<{square:string;x:number;y:number;startX:number;startY:number;pointer:number;active:boolean}|null>(null);
  let suppressClick = false;
  let boardElement = $state<HTMLDivElement>();
  let motion = $state<{to:string;dx:number;dy:number}|null>(null);
  let puzzle = $state<{day:string;hint:string}|null>(null);
  let puzzleSolved = $state(false);
  let puzzleMessage = $state('');
  let streak = $state(0);
  let matchId = $state('');
  let matchToken = '';
  let matchRole = $state<string|null>(null);
  let matchJoined = $state(false);
  let matchRevision = 0;
  let matchClock = $state(0);
  let remaining = $state<Record<string,number>>({white:0,black:0});
  let clockChoice = $state('0');
  let shareURL = $state('');
  let remoteInFlight = false;
  let replayMode = $state(false);
  let reportPoints = $derived(report.map((r,i) => `${report.length > 1 ? i/(report.length-1)*280 : 0},${50-Math.max(-1000,Math.min(1000,r.cp))/25}`).join(' '));
  function effectSound(next: Position) {
    if (!sound) return;
    audio ??= new AudioContext(); void audio.resume();
    const oscillator = audio.createOscillator(), gain = audio.createGain();
    oscillator.connect(gain); gain.connect(audio.destination);
    oscillator.frequency.value = next.check ? 660 : next.captured.white.length + next.captured.black.length > (position?.captured.white.length ?? 0)+(position?.captured.black.length ?? 0) ? 220 : 440;
    gain.gain.setValueAtTime(.035,audio.currentTime); gain.gain.exponentialRampToValueAtTime(.001,audio.currentTime+.09);
    oscillator.start(); oscillator.stop(audio.currentTime+.1);
  }
  function toggleSound() {
    sound = !sound;
    if (sound) { audio ??= new AudioContext(); void audio.resume(); }
    try {localStorage.setItem('chess-sound',String(sound));} catch { /* Optional preference. */ }
  }
  function pointerDown(event: PointerEvent, square: string) {
    if (!interactive || promotion.length || !position?.legal_moves.some(m => m.startsWith(square)) || event.button !== 0) return;
    drag = {square,x:event.clientX,y:event.clientY,startX:event.clientX,startY:event.clientY,pointer:event.pointerId,active:false};
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
  }
  function pointerMove(event: PointerEvent) {
    if (!drag || drag.pointer !== event.pointerId) return;
    if (Math.hypot(event.clientX-drag.startX,event.clientY-drag.startY)>8) { drag.active = true; selected = drag.square; }
    drag.x=event.clientX;drag.y=event.clientY;
  }
  function pointerUp(event: PointerEvent) {
    if (!drag || drag.pointer !== event.pointerId) return;
    const current = drag; drag = null;
    if (!current.active) return;
    suppressClick = true; window.setTimeout(() => suppressClick = false, 0);
    if(!boardElement) return;
    const box = boardElement.getBoundingClientRect();
    const border = Number.parseFloat(getComputedStyle(boardElement).borderLeftWidth);
    const x = Math.floor((event.clientX-box.left-border)/(box.width-2*border)*8);
    const y = Math.floor((event.clientY-box.top-border)/(box.height-2*border)*8);
    if (x>=0 && x<8 && y>=0 && y<8) { selected = current.square; choose(squares[y*8+x]); }
    else selected = null;
  }
  async function jsonRequest(path:string, body?:object) {
    const response = await fetch(path, body === undefined ? {signal:AbortSignal.timeout(15000)} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:AbortSignal.timeout(15000)});
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail==='string' ? data.detail : 'Request failed.');
    return data;
  }
  async function engineAnalysis(body:object): Promise<Analysis> {
    for(let attempt=0;attempt<3;attempt++) {
      try {return await jsonRequest('/api/analyse',body);}
      catch(e) {
        if(attempt===2 || !(e instanceof Error) || !e.message.includes('Stockfish is busy')) throw e;
        await new Promise(resolve=>setTimeout(resolve,300*(attempt+1)));
      }
    }
    throw new Error('Stockfish is busy. Try again in a moment.');
  }
  async function explain() {
    if (!view || analysing) return;
    analysing = true; error = ''; arrow = [];
    const fen = view.fen;
    try { const data = await engineAnalysis({moves:view.moves,initial_fen:view.initial_fen}); if(view?.fen===fen) { analysis=data; arrow=data.lines[0]?.uci[0] ? [data.lines[0].uci[0].slice(0,2),data.lines[0].uci[0].slice(2,4)] : []; } }
    catch(e) {error = String(e instanceof Error ? e.message : e);}
    finally {analysing=false;}
  }
  async function analyseGame() {
    if (!position || reportRunning) return;
    reportRunning=true; report=[]; error='';
    const source = position, generation = ++reportGeneration;
    try {
      let before:Analysis|null=null;
      for(let ply=0;ply<=source.moves.length;ply++) {
        if(generation!==reportGeneration) break;
        const data:Analysis=await engineAnalysis({moves:source.moves.slice(0,ply),initial_fen:source.initial_fen});
        if(generation!==reportGeneration) break;
        const firstWhite = source.initial_fen.split(' ')[1]==='w';
        const whiteMoved = (ply%2===1) === firstWhite;
        const loss=before ? Math.max(0,(before.cp-data.cp)*(whiteMoved?1:-1)) : 0;
        report=[...report,{ply,cp:data.cp,loss,best:before?.lines[0]?.san ?? ''}]; before=data;
      }
    } catch(e) {error=String(e instanceof Error ? e.message : e);}
    finally {if(generation===reportGeneration) reportRunning=false;}
  }
  async function share() {
    if(!position) return;
    try { const data=matchId ? await jsonRequest(`/api/matches/${matchId}/replay`,{}) : await jsonRequest('/api/replays',payload()); shareURL=`${location.origin}/?replay=${data.id}`; notice='Replay link ready. Links last 30 days.'; }
    catch(e) {error=String(e instanceof Error ? e.message : e);}
  }
  async function copyLink() {
    try {await navigator.clipboard.writeText(shareURL); notice='Link copied.';} catch {notice='Select and copy the link below.';}
  }
  function clockText(color:string) {const seconds=Math.ceil(remaining[color]??0); return `${Math.floor(seconds/60)}:${String(seconds%60).padStart(2,'0')}`;}
  function acceptMatch(data: {position:Position;role:string|null;joined:boolean;revision:number;remaining:Record<string,number>;clock:number}) {
    matchRole=data.role;matchJoined=data.joined;matchRevision=data.revision;remaining=data.remaining;matchClock=data.clock;
    if(position?.fen !== data.position.fen || position?.ending !== data.position.ending || position?.result !== data.position.result) accept(data.position);
  }
  async function pollMatch() {
    if(!matchId || remoteInFlight || busy) return;
    remoteInFlight=true;
    try {acceptMatch(await jsonRequest(`/api/matches/${matchId}`,{token:matchToken}));}
    catch(e) {error=String(e instanceof Error ? e.message : e);}
    finally {remoteInFlight=false;}
  }
  async function createMatch() {
    if(!resetAllowed()) return;
    busy=true;error='';
    try {const data=await jsonRequest('/api/matches',{clock:Number(clockChoice)}); matchId=data.id;matchToken=data.token;localStorage.setItem(`chess-match-${matchId}`,matchToken); opponent='local';puzzle=null;replayMode=false;reviewed=null;shareURL=`${location.origin}/?match=${matchId}`;history.replaceState(null,'',`?match=${matchId}`);acceptMatch(await jsonRequest(`/api/matches/${matchId}`,{token:matchToken}));notice='Send the invitation link to your friend.';}
    catch(e) {error=String(e instanceof Error ? e.message : e);}
    finally {busy=false;}
  }
  async function joinMatch() {
    busy=true;error='';
    try {const data=await jsonRequest(`/api/matches/${matchId}/join`,{});matchToken=data.token;localStorage.setItem(`chess-match-${matchId}`,matchToken);acceptMatch(data);flipped=true;}
    catch(e) {error=String(e instanceof Error ? e.message : e);}
    finally {busy=false;}
  }
  async function startPuzzle() {
    if(!resetAllowed()) return;
    busy=true;error='';
    try {const data=await jsonRequest('/api/puzzle');matchId='';matchToken='';replayMode=false;history.replaceState(null,'','/');opponent='local';puzzle={day:data.day,hint:data.hint};puzzleSolved=false;puzzleMessage='Find mate in one.';shareURL='';accept(data.position);}
    catch(e) {error=String(e instanceof Error ? e.message : e);}
    finally {busy=false;}
  }
  function solveStreak(day:string) {
    try {
      const saved=JSON.parse(localStorage.getItem('chess-puzzle-streak')??'{}');
      if(saved.day!==day) {const previous=new Date(`${day}T00:00:00Z`);previous.setUTCDate(previous.getUTCDate()-1);streak=saved.day===previous.toISOString().slice(0,10) ? (Number(saved.streak)||0)+1 : 1;localStorage.setItem('chess-puzzle-streak',JSON.stringify({day,streak}));}
      else streak=Number(saved.streak)||1;
    } catch {streak=1;}
  }
  function arrowPoint(square:string) {const index=squares.indexOf(square);return {x:index%8*12.5+6.25,y:Math.floor(index/8)*12.5+6.25};}
  const storageKey = 'aaryan-chess-v1';
  let view = $derived(reviewed ?? position);
  let engineTurn = $derived(opponent === 'stockfish' && position?.turn !== humanColor && !position?.result);
  let interactive = $derived(!!position && !busy && !reviewed && !position.result && !engineTurn && !replayMode && !puzzleSolved && (!matchId || (matchJoined && matchRole === position.turn)));
  let squares = $derived(Array.from({ length:64 }, (_, i) => {
    const index = flipped ? 63 - i : i;
    return 'abcdefgh'[index % 8] + (8 - Math.floor(index / 8));
  }));
  let targets = $derived(interactive ? position?.legal_moves.filter(m => m.slice(0,2) === selected).map(m => m.slice(2,4)) ?? [] : []);
  let castleRooks = $derived(interactive && selected && ['e1','e8'].includes(selected) && position?.pieces[selected]?.toLowerCase() === 'k'
    ? position.legal_moves.filter(m => m.slice(0,2) === selected && ['g','c'].includes(m[2])).map(m => (m[2] === 'g' ? 'h' : 'a') + m[3]) : []);
  let pairs = $derived.by(() => {
    const rows: {number:number; white?:string; black?:string; whitePly:number; blackPly:number}[] = [];
    const fields = position?.initial_fen.split(' ') ?? [];
    const offset = fields[1] === 'b' ? 1 : 0;
    const start = Number(fields[5] ?? 1);
    position?.moves.forEach((move, i) => {
      const rowIndex = Math.floor((i + offset) / 2);
      const row = rows[rowIndex] ?? {number:start+rowIndex, whitePly:0, blackPly:0};
      if ((i + offset) % 2 === 0) { row.white = move; row.whitePly = i + 1; }
      else { row.black = move; row.blackPly = i + 1; }
      rows[rowIndex] = row;
    });
    return rows;
  });
  let status = $derived(view?.result ? `${view.result} · ${view.termination}` : `${view?.turn === 'black' ? 'Black' : 'White'} to move${view?.check ? ' · Check' : ''}${reviewed ? ' · Review' : ''}`);

  function toggleTheme() {
    light = !light;
    document.documentElement.classList.toggle('light', light);
    try { localStorage.setItem('chess-theme', light ? 'light' : 'dark'); } catch { /* Theme remains usable without storage. */ }
  }
  function persist() {
    if (!position || matchId || puzzle || replayMode) return;
    try { localStorage.setItem(storageKey, JSON.stringify({ moves:position.moves, initial_fen:position.initial_fen, ending:position.ending, opponent, humanColor, difficulty })); }
    catch { notice = 'Browser storage is unavailable. Export PGN to save your game.'; }
  }
  function payload(moves = position?.moves ?? []) {
    return { moves, ...(position ? {initial_fen:position.initial_fen, ending:position.ending} : {}) };
  }
  async function request(path: string, body: object): Promise<Position> {
    const response = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body), signal:AbortSignal.timeout(15000)});
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'The game could not be loaded.');
    return data;
  }
  function accept(next: Position) {
    if(position && next.fen!==position.fen) {reportGeneration++;reportRunning=false;report=[];}
    if(position && next.moves.length === position.moves.length+1) {
      effectSound(next);
      const from=next.last_move[0],to=next.last_move[1];
      if(from && to) {const a=arrowPoint(from),b=arrowPoint(to); motion={to,dx:(a.x-b.x)*8/100,dy:(a.y-b.y)*8/100};}
    } else motion=null;
    analysis=null;arrow=[];
    position = next; reviewed = null; reviewPly = next.moves.length; selected = null; promotion = []; notation = ''; persist();
  }
  async function reply() {
    if (opponent === 'stockfish' && position && position.turn !== humanColor && !position.result) {
      accept(await request('/api/engine-move', {...payload(), difficulty}));
    }
  }
  async function load(moves: string[], move?: string, overrides: object = {}) {
    if (busy) return;
    busy = true; error = ''; notice = '';
    try {
      if(matchId) {
        acceptMatch(await jsonRequest(`/api/matches/${matchId}`,{token:matchToken,revision:matchRevision,...(move?{move}:{}),...(('action' in overrides)?{action:(overrides as {action:string}).action}:{})}));
        return;
      }
      if(puzzle && move) {
        const data=await jsonRequest('/api/puzzle',{day:puzzle.day,move});
        if(data.correct) {accept(data.position);puzzleSolved=true;puzzleMessage='Solved. Come back tomorrow.';solveStreak(puzzle.day);}
        else {puzzleMessage='That is legal, but there is a stronger move. Try again.';selected=null;promotion=[];}
        return;
      }
      accept(await request('/api/position', { ...payload(moves), ...(move ? {move} : {}), ...overrides }));
      await reply();
    } catch (e) { error = e instanceof Error ? e.message : 'Unable to reach the chess service.'; }
    finally { busy = false; }
  }
  onMount(() => {
    try { light = localStorage.getItem('chess-theme') === 'light'; } catch { /* Default dark theme. */ }
    document.documentElement.classList.toggle('light', light);
    void checkEngine();
    const enginePoll = window.setInterval(() => { void checkEngine(); }, 5000);
    window.addEventListener('focus', checkEngine);
    let moves: string[] = [];
    let overrides: Record<string, unknown> = {};
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) ?? '[]');
      if (Array.isArray(saved) && saved.every(m => typeof m === 'string')) moves = saved;
      else if (saved && Array.isArray(saved.moves) && saved.moves.every((m: unknown) => typeof m === 'string')) {
        moves = saved.moves;
        if (typeof saved.initial_fen === 'string') overrides.initial_fen = saved.initial_fen;
        if (saved.ending) overrides.ending = saved.ending;
        opponent = saved.opponent === 'stockfish' ? 'stockfish' : 'local';
        humanColor = saved.humanColor === 'black' ? 'black' : 'white';
        difficulty = ['easy','medium','hard'].includes(saved.difficulty) ? saved.difficulty : 'medium';
        flipped = opponent === 'stockfish' && humanColor === 'black';
      }
    } catch { /* Start fresh if local storage is malformed. */ }
    try {sound=localStorage.getItem('chess-sound')==='true';streak=Number(JSON.parse(localStorage.getItem('chess-puzzle-streak')??'{}').streak)||0;} catch { /* Optional preferences. */ }
    const params=new URLSearchParams(location.search);
    const remotePoll=window.setInterval(() => {void pollMatch();},1000);
    async function initialize() {
      try {
        if(params.has('match')) {matchId=params.get('match')!;matchToken=localStorage.getItem(`chess-match-${matchId}`)??'';opponent='local';await pollMatch();flipped=matchRole==='black';}
        else if(params.has('replay')) {replayMode=true;opponent='local';accept(await jsonRequest(`/api/replays/${params.get('replay')}`));notice='Shared replay · use the move journal to explore.';}
        else await load(moves,undefined,overrides);
      } catch(e) {error=String(e instanceof Error ? e.message : e);}
    }
    void initialize();
    return () => { window.clearInterval(enginePoll);window.clearInterval(remotePoll);reportGeneration++;void audio?.close(); window.removeEventListener('focus', checkEngine); };
  });
  function choose(square: string) {
    if (!interactive || !position || promotion.length) return;
    let destination = square;
    // Accept the common king-then-rook gesture as well as king-to-g/c.
    if (selected && ['e1','e8'].includes(selected) && position.pieces[selected]?.toLowerCase() === 'k'
      && position.pieces[square]?.toLowerCase() === 'r' && selected[1] === square[1]
      && (position.pieces[selected] === position.pieces[selected].toUpperCase()) === (position.pieces[square] === position.pieces[square].toUpperCase())) {
      if (square[0] === 'h') destination = 'g' + square[1];
      if (square[0] === 'a') destination = 'c' + square[1];
    }
    const candidates = position.legal_moves.filter(m => m.slice(0,2) === selected && m.slice(2,4) === destination);
    if (candidates.length > 1) { promotion = candidates; return; }
    if (candidates.length === 1) { void load(position.moves, candidates[0]); return; }
    const piece = position.pieces[square];
    const own = piece && (piece === piece.toUpperCase()) === (position.turn === 'white');
    selected = own && selected !== square ? square : null;
  }
  function download() {
    if (!position) return;
    const url = URL.createObjectURL(new Blob([position.pgn], {type:'application/x-chess-pgn'}));
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'aaryan-chess.pgn'; anchor.click(); URL.revokeObjectURL(url);
  }
  function resetAllowed() { return !position?.moves.length && !position?.ending || window.confirm('Start a new game? Your current game will be replaced.'); }
  function newGame() { if (resetAllowed()) {matchId='';matchToken='';puzzle=null;puzzleSolved=false;replayMode=false;shareURL='';reportGeneration++;reportRunning=false;report=[];history.replaceState(null,'','/');void load([], undefined, {initial_fen:undefined, ending:null});} }
  function changeSetup(event: Event, field: 'opponent' | 'humanColor') {
    reportGeneration++;reportRunning=false;report=[];
    const control = event.target as HTMLSelectElement;
    if (!resetAllowed()) { control.value = field === 'opponent' ? opponent : humanColor; return; }
    if (field === 'opponent') opponent = control.value; else humanColor = control.value;
    flipped = opponent === 'stockfish' && humanColor === 'black';
    void load([], undefined, {initial_fen:undefined, ending:null});
  }
  function undo() {
    if (!position) return;
    // In computer games, take back the player's move and its reply together.
    const count = opponent === 'stockfish' && position.turn === humanColor ? 2 : 1;
    void load(position.moves.slice(0, Math.max(0, position.moves.length - count)), undefined, {ending:null});
  }
  async function review(ply: number) {
    if (!position || busy || ply < 0 || ply > position.moves.length) return;
    selected = null; promotion = [];analysis=null;arrow=[];
    if (ply === position.moves.length) { reviewed = null; reviewPly = ply; return; }
    busy = true; error = '';
    try { reviewed = await request('/api/position', {...payload(), review_ply:ply}); reviewPly = ply; }
    catch (e) { error = e instanceof Error ? e.message : 'Unable to review the game.'; }
    finally { busy = false; }
  }
  function finish(action: 'resign' | 'claim_draw') {
    if (!interactive || !position) return;
    if (action === 'resign' && !window.confirm(`Resign as ${position.turn}?`)) return;
    void load(position.moves, undefined, {action});
  }
  async function importGame() {
    if (!pgnText.trim() || busy) return;
    if ((position?.moves.length || position?.ending) && !window.confirm('Replace your current game with this PGN?')) return;
    busy = true; importError = '';
    try {
      const next = await request('/api/import', {pgn:pgnText});
      opponent = 'local';matchId='';puzzle=null;puzzleSolved=false;replayMode=false;history.replaceState(null,'','/'); accept(next); importing = false; pgnText = ''; error = '';
    } catch (e) { importError = e instanceof Error ? e.message : 'Invalid PGN.'; }
    finally { busy = false; }
  }
  async function readPgn(event: Event) {
    const file = (event.target as HTMLInputElement).files?.[0];
    if (!file) return;
    if (file.size > 60000) { importError = 'PGN files must be under 60 KB.'; return; }
    pgnText = await file.text(); importError = '';
  }
  function material(color: string) {
    const balance = (view?.material_balance ?? 0) * (color === 'white' ? 1 : -1);
    return balance > 0 ? `+${balance}` : '';
  }
</script>

<svelte:head><title>Chess — Aaryan Dehade</title></svelte:head>
<div class="ambient-background" aria-hidden="true"><div class="ambient-orbit"><span class="ambient-blob blob-one"></span><span class="ambient-blob blob-two"></span></div><div class="grain-layer"></div></div>
<a class="skip-link" href="#game">Skip to game</a>
<header><a class="brand" href="/"><img src="/aaryandehade-logo.png" width="40" height="40" alt=""/><span>chess<span class="brand-period">.</span></span></a><nav aria-label="Main navigation"><a class="quiet-link" href="https://apps.aaryandehade.com">All apps ↗</a><button class="theme-toggle" onclick={toggleTheme} aria-label={light ? 'Switch to dark mode' : 'Switch to light mode'}>{light ? '☾' : '☀'}</button></nav></header>
{#if drag?.active && view?.pieces[drag.square]}{@const piece=view.pieces[drag.square]}<span class="drag-piece piece" class:white={piece===piece.toUpperCase()} style:left={`${drag.x}px`} style:top={`${drag.y}px`} aria-hidden="true">{glyphs[piece]}</span>{/if}
<main>
  <div class="workspace" id="game">
    <section class="board-panel" aria-label="Chess game">
      <div class="player"><span class="avatar">{flipped ? '♔' : '♚'}</span><div><strong>{flipped ? 'White' : 'Black'}</strong><span class="captured-pieces" aria-label="Captured by top player">{(view?.captured?.[flipped ? 'white' : 'black'] ?? []).map(p => glyphs[p]).join('')} <span class="material">{material(flipped ? 'white' : 'black')}</span></span></div><span class="player-tag">{matchClock ? clockText(flipped ? 'white' : 'black') : ''} {view?.turn === (flipped ? 'white' : 'black') && !view?.result ? 'TO MOVE' : ''}</span></div>
      <div class="board" bind:this={boardElement} aria-label="Chessboard" aria-busy={busy}>
        {#each squares as square, i}
          {@const piece = view?.pieces[square]}
          <button class="square" class:dark={(Math.floor(i/8) + i%8)%2 === 1} class:selected={selected === square} class:target={targets.includes(square)} class:last-move={view?.last_move?.includes(square)} class:checked={view?.checked_king === square} class:castle-option={castleRooks.includes(square)} title={castleRooks.includes(square) ? 'Castle with this rook' : undefined} disabled={!interactive || promotion.length > 0} onpointerdown={(e) => pointerDown(e,square)} onpointermove={pointerMove} onpointerup={pointerUp} onpointercancel={() => drag=null} onclick={() => {if(!suppressClick) choose(square);}} aria-label={`${square}${piece ? ` ${piece === piece.toUpperCase() ? 'white' : 'black'} ${names[piece.toLowerCase()]}` : ' empty'}${targets.includes(square) ? ', legal destination' : ''}`} data-last-move={view?.last_move?.includes(square) || undefined} data-checked={view?.checked_king === square || undefined} aria-pressed={selected === square}>
            {#if i%8 === 0}<span class="rank">{square[1]}</span>{/if}
            {#if piece}{#key `${piece}-${square}-${view?.moves.length}` }<span class="piece" class:white={piece === piece.toUpperCase()} class:drag-source={drag?.active && drag.square===square} in:fly={{x:motion?.to===square ? motion.dx*(boardElement?.clientWidth??0)/8 : 0,y:motion?.to===square ? motion.dy*(boardElement?.clientHeight??0)/8 : 0,duration:!prefersReducedMotion.current && motion?.to===square?180:0,opacity:1}}>{glyphs[piece]}</span>{/key}{/if}
            {#if targets.includes(square)}<span class="hint" class:capture={!!piece}></span>{/if}
            {#if i >= 56}<span class="file">{square[0]}</span>{/if}
          </button>
        {/each}
        {#if arrow.length===2}
          {@const a=arrowPoint(arrow[0])}{@const b=arrowPoint(arrow[1])}
          <svg class="board-arrows" viewBox="0 0 100 100" aria-label="Suggested move arrow"><defs><marker id="arrowhead" markerWidth="4" markerHeight="4" refX="3" refY="2" orient="auto"><path d="M0,0 L4,2 L0,4" fill="#61300f"/></marker></defs><line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#61300f" stroke-width="1.5" marker-end="url(#arrowhead)"/></svg>
        {/if}
      </div>
      <div class="player"><span class="avatar light">{flipped ? '♚' : '♔'}</span><div><strong>{flipped ? 'Black' : 'White'}</strong><span class="captured-pieces" aria-label="Captured by bottom player">{(view?.captured?.[flipped ? 'black' : 'white'] ?? []).map(p => glyphs[p]).join('')} <span class="material">{material(flipped ? 'black' : 'white')}</span></span></div><span class="player-tag">{matchClock ? clockText(flipped ? 'black' : 'white') : ''} {view?.turn === (flipped ? 'black' : 'white') && !view?.result ? 'TO MOVE' : ''}</span></div>
    </section>
    <aside>
      <section class="game-card"><p class="eyebrow">ON THE BOARD</p><h2 aria-live="polite">{position ? status : 'Loading game…'}</h2><p class="help">{reviewed ? `Reviewing ${reviewPly} of ${position?.moves.length} plies. Return to live to play.` : busy && engineTurn ? 'Stockfish is thinking…' : opponent === 'stockfish' ? `You play ${humanColor} · Stockfish ${difficulty}` : selected ? castleRooks.length ? 'Choose a highlighted square or the rook to castle.' : `Choose a highlighted square to move from ${selected}.` : 'Select a piece to see its legal moves.'}</p>
        {#if promotion.length}<div class="promotion"><p>Choose your promotion</p>{#each promotion as move}<button disabled={busy} onclick={() => load(position!.moves, move)}>{names[move[4]]}</button>{/each}<button onclick={() => promotion = []}>Cancel</button></div>{/if}
        {#if error}<p class="error" role="alert">{error}</p><button onclick={() => load(position?.moves ?? [])} disabled={busy}>Retry</button>{/if}
        {#if notice}<p class="help" role="status">{notice}</p>{/if}
        {#if shareURL}<label for="share-link">Share link</label><input id="share-link" class="share-link" readonly value={shareURL}/><button class="export" onclick={copyLink}>Copy link</button>{/if}

        <div class="actions"><button class="primary" disabled={busy} onclick={newGame}>New game <span>↗</span></button><button disabled={!!matchId || !!puzzle || replayMode || !position?.moves.length || busy || !!reviewed || (opponent === 'stockfish' && humanColor === 'black' && position.moves.length === 1)} onclick={undo}>↶ Undo</button><button onclick={() => flipped = !flipped}>⇅ Flip board</button></div>
        {#if matchId}<p class="help">{matchRole ? `You play ${matchRole}${matchJoined?'':' · Waiting for a friend'}` : matchJoined ? 'Watching this match' : 'Invitation to play Black'}</p>{#if !matchRole && !matchJoined}<button disabled={busy} onclick={joinMatch}>Join match</button>{/if}{/if}
        {#if puzzle}<p class="help" role="status">{puzzleMessage} · {streak} day streak</p><button onclick={() => puzzleMessage=puzzle!.hint}>Puzzle hint</button>{/if}
        <div class="end-actions"><button disabled={!interactive} onclick={() => finish('resign')}>Resign</button><button disabled={!interactive || !position?.can_claim_draw} onclick={() => finish('claim_draw')}>Claim draw</button></div>
        <details class="setup" ontoggle={() => { void checkEngine(); }}><summary>Game settings</summary><label for="opponent">Opponent</label><select id="opponent" value={opponent} disabled={busy || !!matchId || !!puzzle || replayMode} onchange={(e) => changeSetup(e, 'opponent')}><option value="local">Local two-player</option><option value="stockfish" disabled={!engineAvailable}>Stockfish{engineAvailable ? '' : engineChecking ? ' (checking…)' : ' (unavailable)'}</option></select>{#if opponent === 'stockfish'}<label for="side">Play as</label><select id="side" value={humanColor} disabled={busy} onchange={(e) => changeSetup(e, 'humanColor')}><option value="white">White</option><option value="black">Black</option></select><label for="difficulty">Difficulty</label><select id="difficulty" bind:value={difficulty} disabled={busy} onchange={persist}><option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option></select>{/if}<button class="export" onclick={toggleSound}>{sound?'Mute sounds':'Enable sounds'}</button>
          <label for="friend-clock">Friend match clock</label><select id="friend-clock" bind:value={clockChoice}><option value="0">No clock</option><option value="180">3 minutes</option><option value="300">5 minutes</option><option value="600">10 minutes</option></select><button class="export" disabled={busy} onclick={createMatch}>Invite a friend ↗</button>
          <button class="export" disabled={busy} onclick={startPuzzle}>Daily puzzle ↗</button>
        </details>
      </section>
      <section class="history-card"><div class="card-heading"><h3>Move journal</h3><span>{position?.moves.length ?? 0} PLIES</span></div><div class="history">{#if !pairs.length}<div class="empty"><span>♙</span><p>Every great game starts<br/>with a single move.</p></div>{:else}{#each pairs as pair}<div class="move-row"><span>{pair.number}.</span><button class:active={reviewed && reviewPly === pair.whitePly} aria-label={`Review ply ${pair.whitePly}: ${pair.white}`} disabled={busy || !pair.white} onclick={() => review(pair.whitePly)}>{pair.white ?? '—'}</button><button class:active={reviewed && reviewPly === pair.blackPly} aria-label={`Review ply ${pair.blackPly}: ${pair.black ?? 'empty'}`} disabled={busy || !pair.black} onclick={() => review(pair.blackPly)}>{pair.black ?? '—'}</button></div>{/each}{/if}</div>
        <div class="review-controls"><button aria-label="First position" disabled={busy || !position?.moves.length || (reviewed !== null && reviewPly === 0)} onclick={() => review(0)}>⏮</button><button aria-label="Previous position" disabled={busy || !position?.moves.length || (reviewed !== null && reviewPly === 0)} onclick={() => review((reviewed ? reviewPly : position!.moves.length)-1)}>‹</button><button aria-label="Next position" disabled={busy || !reviewed} onclick={() => review(reviewPly+1)}>›</button><button disabled={busy || !reviewed} onclick={() => review(position!.moves.length)}>Live ↗</button></div>
        <form onsubmit={(event) => {event.preventDefault(); if (notation.trim()) void load(position?.moves ?? [], notation.trim());}}><label for="notation">Or enter a move</label><div class="input-row"><input id="notation" bind:value={notation} placeholder="e4, Nf3, e2e4…" autocomplete="off" maxlength="16" disabled={!interactive}/><button type="submit" aria-label="Play entered move" disabled={!interactive || !notation.trim()}>→</button></div></form><button class="export" disabled={!position || busy} onclick={download}>↓ Export PGN</button><button class="export import-button" disabled={busy} onclick={() => {importing = !importing; importError = '';}}>↑ Import PGN</button>
        {#if importing}<form class="import-form" onsubmit={(e) => {e.preventDefault(); void importGame();}}><label for="pgn">Paste one PGN game</label><textarea id="pgn" bind:value={pgnText} maxlength="60000" rows="5" disabled={busy}></textarea><label for="pgn-file">Or choose a PGN file</label><input id="pgn-file" type="file" accept=".pgn,text/plain,application/x-chess-pgn" onchange={readPgn} disabled={busy}/>{#if importError}<p class="error" role="alert">{importError}</p>{/if}<button class="import-submit" type="submit" disabled={busy || !pgnText.trim()}>Import game</button></form>{/if}
      </section>
      <section class="history-card tools-card"><details><summary>Explore & share</summary>
        <div class="tool-actions"><button disabled={!view || analysing || (!!matchId && !position?.result) || (!!puzzle && !puzzleSolved) || (opponent==='stockfish' && !position?.result && !reviewed)} onclick={explain}>{analysing?'Analysing…':'Explain this position'}</button><button disabled={!position?.moves.length || reportRunning || !position?.result} onclick={analyseGame}>{reportRunning?`Analysing ${report.length}/${(position?.moves.length??0)+1}…`:'Analyse finished game'}</button>{#if reportRunning}<button onclick={() => {reportGeneration++;reportRunning=false;}}>Stop analysis</button>{/if}<button disabled={!position || busy || !!puzzle} onclick={share}>Share replay ↗</button></div>
        {#if analysis}<p class="help">White evaluation: {analysis.mate!==null ? `Mate ${analysis.mate}` : (analysis.cp/100).toFixed(2)}. Short Stockfish analysis.</p>{#each analysis.lines as line}<button class="candidate" onclick={() => arrow=line.uci[0]?[line.uci[0].slice(0,2),line.uci[0].slice(2,4)]:[]}>{line.san || 'No legal moves'} · {line.mate!==null?`M${line.mate}`:(line.cp/100).toFixed(2)}<span class="candidate-explanation">{line.explanation}</span></button>{/each}{#if analysis.threats.length}<p class="help">Attacked and undefended: {analysis.threats.map(t=>`${t.piece} on ${t.square}`).join(', ')}. These pieces may be tactically protected.</p>{/if}<p class="help">The arrow shows the candidate move; the line shows Stockfish’s expected reply. Scores favor White when positive.</p>{/if}
        {#if report.length}<svg class="evaluation-chart" viewBox="0 0 280 100" role="img" aria-label="Game evaluation graph, positive favors White"><line x1="0" y1="50" x2="280" y2="50" stroke="currentColor" opacity=".3"/><polyline points={reportPoints} fill="none" stroke="#ff7a30" stroke-width="2"/></svg><p class="help">White evaluation · capped at ±10 pawns. Short analysis is approximate.</p><div class="analysis-list">{#each report.filter(r=>r.loss>=100) as item}<button class="candidate" onclick={() => review(item.ply-1)}>Ply {item.ply}: {item.loss>=300?'Blunder':'Mistake'} · lost {(item.loss/100).toFixed(1)} pawns. Try {item.best}</button>{/each}</div>{/if}

      </details></section>
    </aside>
  </div>
  <footer><span>Built for the love of the game.</span><a href="https://aaryandehade.com">Aaryan Dehade · © {new Date().getFullYear()}</a></footer>
</main>
