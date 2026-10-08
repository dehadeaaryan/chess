import { readFile } from 'node:fs/promises';
import { test, expect, type Page } from '@playwright/test';

const heading = (page: Page) => page.getByRole('heading', { level: 2 });
async function openGame(page: Page, moves: string[] = []) {
  await page.addInitScript((moves) => localStorage.setItem('aaryan-chess-v1', JSON.stringify(moves)), moves);
  await page.goto('/');
  await expect(heading(page)).not.toHaveText('Loading game…');
}
async function play(page: Page, move: string) {
  await page.getByLabel('Or enter a move').fill(move);
  await page.getByRole('button', { name: 'Play entered move', exact: true }).click();
  await expect(page.getByLabel('Or enter a move')).toHaveValue('');
}

test('legal hints, board moves, undo, flip and refresh persistence', async ({ page }) => {
  await page.goto('/');
  await expect(heading(page)).toHaveText('White to move');
  await expect(page.locator('.square')).toHaveCount(64);
  await page.getByRole('button', { name: 'e2 white pawn', exact: true }).click();
  await expect(page.getByRole('button', { name: 'e4 empty, legal destination', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'e4 empty, legal destination', exact: true }).click();
  await expect(heading(page)).toHaveText('Black to move');
  await expect(page.getByRole('button', { name: 'e4 white pawn', exact: true })).toBeVisible();
  await play(page, 'e5');
  await page.reload();
  await expect(heading(page)).toHaveText('White to move');
  await expect(page.locator('.move-row')).toHaveText(['1.e4e5']);
  await page.getByRole('button', { name: 'Undo' }).click();
  await expect(heading(page)).toHaveText('Black to move');
  await page.getByRole('button', { name: 'Flip board' }).click();
  await expect(page.locator('.square').first()).toHaveAttribute('aria-label', 'h1 white rook');
});

test('illegal notation is rejected and a legal move recovers', async ({ page }) => {
  await page.goto('/');
  await expect(heading(page)).toHaveText('White to move');
  await page.getByLabel('Or enter a move').fill('e2e5');
  await page.getByRole('button', { name: 'Play entered move' }).click();
  await expect(page.getByRole('alert')).toContainText('Illegal move');
  await expect(heading(page)).toHaveText('White to move');
  await play(page, 'e4');
  await expect(page.getByRole('alert')).toHaveCount(0);
});

test('promotion allows an underpromotion', async ({ page }) => {
  await openGame(page, ['a4','h5','a5','h4','a6','h3','axb7','hxg2']);
  await page.getByRole('button', { name: 'b7 white pawn', exact: true }).click();
  await page.getByRole('button', { name: 'a8 black rook, legal destination', exact: true }).click();
  await expect(page.getByText('Choose your promotion')).toBeVisible();
  await page.getByRole('button', { name: 'knight', exact: true }).click();
  await expect(page.getByRole('button', { name: 'a8 white knight', exact: true })).toBeVisible();
  await expect(heading(page)).toHaveText('Black to move');
});

test('checkmate stops play, PGN downloads, and new game resets', async ({ page }) => {
  await openGame(page, ['f3','e5','g4','Qh4#']);
  await expect(heading(page)).toHaveText('0-1 · checkmate');
  await expect(page.getByRole('button', { name: 'e2 white pawn', exact: true })).toBeDisabled();
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export PGN' }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe('aaryan-chess.pgn');
  const pgn = await readFile((await download.path())!, 'utf8');
  expect(pgn).toContain('1. f3 e5 2. g4 Qh4# 0-1');
  page.once('dialog', dialog => dialog.accept());
  await page.getByRole('button', { name: 'New game' }).click();
  await expect(heading(page)).toHaveText('White to move');
  await expect(page.locator('.move-row')).toHaveCount(0);
});

test('network errors preserve the game and retry recovers', async ({ page }) => {
  await page.goto('/');
  await expect(heading(page)).toHaveText('White to move');
  await page.route('**/api/position', route => route.abort());
  await page.getByLabel('Or enter a move').fill('e4');
  await page.getByRole('button', { name: 'Play entered move' }).click();
  await expect(page.getByRole('alert')).toBeVisible();
  await expect(heading(page)).toHaveText('White to move');
  await page.unroute('**/api/position');
  await page.getByRole('button', { name: 'Retry', exact: true }).click();
  await expect(page.getByRole('alert')).toHaveCount(0);
  await play(page, 'e4');
  await expect(heading(page)).toHaveText('Black to move');
});

test('shared theme, keyboard controls and responsive layout', async ({ page }, testInfo) => {
  await page.goto('/');
  await expect(heading(page)).toHaveText('White to move');
  await expect(page.locator('body')).toHaveCSS('font-family', /Figtree/);
  await page.getByRole('button', { name: 'Switch to light mode' }).click();
  await expect(page.locator('html')).toHaveClass('light');
  await page.reload();
  await expect(page.getByRole('button', { name: 'Switch to dark mode' })).toBeVisible();
  await page.getByRole('button', { name: 'Switch to dark mode' }).click();
  await page.getByRole('button', { name: 'e2 white pawn', exact: true }).focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('button', { name: 'e4 empty, legal destination', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'e4 empty, legal destination', exact: true }).focus();
  await page.keyboard.press('Enter');
  await expect(heading(page)).toHaveText('Black to move');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('chess-dark.png'), fullPage: true });
  await page.getByRole('button', { name: 'Switch to light mode' }).click();
  await page.screenshot({ path: testInfo.outputPath('chess-light.png'), fullPage: true });
});

test('last move, checked king, captured pieces and material are visible', async ({ page }) => {
  await openGame(page, ['e4','d5','exd5']);
  await expect(page.locator('[data-last-move="true"]')).toHaveCount(2);
  await expect(page.getByRole('button', { name: 'd5 white pawn', exact:true })).toHaveAttribute('data-last-move','true');
  await expect(page.getByLabel('Captured by bottom player')).toContainText('+1');
  await page.getByRole('button', { name: 'Undo' }).click();
  await expect(page.getByLabel('Captured by bottom player')).not.toContainText('+1');
  await page.getByRole('button', { name: 'Import PGN' }).click();
  await page.getByLabel('Paste one PGN game').fill('1. f3 e5 2. g4 Qh4# 0-1');
  page.once('dialog', dialog => dialog.accept());
  await page.getByRole('button', { name:'Import game', exact:true }).click();
  await expect(page.getByRole('button', {name:'e1 white king',exact:true})).toHaveAttribute('data-checked','true');
});

test('review preserves the live game and return to live allows play', async ({ page }) => {
  await openGame(page, ['e4','e5','Nf3']);
  await page.getByRole('button', {name:'Review ply 1: e4',exact:true}).click();
  await expect(heading(page)).toHaveText('Black to move · Review');
  await expect(page.getByRole('button', {name:'e7 black pawn',exact:true})).toBeVisible();
  await expect(page.getByLabel('Or enter a move')).toBeDisabled();
  await expect(page.getByRole('button', {name:'Undo'})).toBeDisabled();
  await expect(page.locator('.move-row')).toHaveCount(2);
  await page.getByRole('button', {name:'Next position'}).click();
  await expect(heading(page)).toHaveText('White to move · Review');
  await page.getByRole('button', {name:'Live'}).click();
  await expect(heading(page)).toHaveText('Black to move');
  await play(page,'Nc6');
  await expect(page.locator('.move-row')).toHaveText(['1.e4e5','2.Nf3Nc6']);
});

test('resignation persists across refresh and PGN export', async ({ page }) => {
  await page.goto('/');
  await expect(heading(page)).toHaveText('White to move');
  page.once('dialog', dialog => dialog.accept());
  await page.getByRole('button', {name:'Resign',exact:true}).click();
  await expect(heading(page)).toHaveText('0-1 · resignation');
  await page.reload();
  await expect(heading(page)).toHaveText('0-1 · resignation');
  const waiting = page.waitForEvent('download');
  await page.getByRole('button', {name:'Export PGN'}).click();
  const pgn = await readFile((await (await waiting).path())!, 'utf8');
  expect(pgn).toContain('[Result "0-1"]');
});

test('draw claim is enabled only when valid and ends the game', async ({ page }) => {
  await page.goto('/');
  await expect(heading(page)).toHaveText('White to move');
  await expect(page.getByRole('button', {name:'Claim draw'})).toBeDisabled();
  for (const move of ['Nf3','Nf6','Ng1','Ng8','Nf3','Nf6','Ng1','Ng8']) await play(page,move);
  await expect(page.getByRole('button', {name:'Claim draw'})).toBeEnabled();
  await page.getByRole('button', {name:'Claim draw'}).click();
  await expect(heading(page)).toHaveText('1/2-1/2 · draw claimed');
  await page.reload();
  await expect(heading(page)).toHaveText('1/2-1/2 · draw claimed');
});

test('PGN import validates input, supports files and custom starting positions', async ({ page }) => {
  await page.goto('/');
  await expect(heading(page)).toHaveText('White to move');
  await page.getByRole('button',{name:'Import PGN'}).click();
  await page.getByLabel('Paste one PGN game').fill('not a PGN');
  await page.getByRole('button',{name:'Import game',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('Invalid PGN');
  await page.getByLabel('Or choose a PGN file').setInputFiles({name:'example.pgn',mimeType:'text/plain',buffer:Buffer.from('1. e4 e5 2. Nf3 *')});
  await page.getByRole('button',{name:'Import game',exact:true}).click();
  await expect(heading(page)).toHaveText('Black to move');
  await expect(page.locator('.move-row')).toHaveCount(2);
  await page.getByRole('button',{name:'Import PGN'}).click();
  await page.getByLabel('Paste one PGN game').fill('[SetUp "1"]\n[FEN "7k/8/8/8/8/8/8/R5K1 b - - 0 12"]\n[Result "*"]\n\n12... Kh7 *');
  page.once('dialog',dialog => dialog.accept());
  await page.getByRole('button',{name:'Import game',exact:true}).click();
  await expect(page.locator('.move-row')).toHaveText(['12.—Kh7']);
  await page.getByRole('button',{name:'First position'}).click();
  await expect(page.getByRole('button',{name:'h8 black king',exact:true})).toBeVisible();
});

test('Stockfish plays both colors, difficulty changes and undo restores a turn', async ({ page }) => {
  await page.goto('/');
  await expect(heading(page)).toHaveText('White to move');
  await page.getByText('Game settings', {exact:true}).click();
  await expect(page.locator('#opponent option[value="stockfish"]')).toBeEnabled();
  await page.getByLabel('Opponent', {exact:true}).selectOption('stockfish');
  await expect(page.getByLabel('Difficulty')).toBeVisible();
  await page.getByLabel('Difficulty').selectOption('easy');
  await play(page,'e4');
  await expect(heading(page)).toHaveText('White to move');
  await expect(page.locator('.move-row').first()).toContainText('e4');
  await expect(page.locator('.move-row').first().locator('button').last()).not.toHaveText('—');
  await page.getByRole('button',{name:'Undo'}).click();
  await expect(page.locator('.move-row')).toHaveCount(0);
  await page.getByLabel('Play as').selectOption('black');
  await expect(heading(page)).toHaveText('Black to move');
  await expect(page.locator('.square').first()).toHaveAttribute('aria-label','h1 white rook');
  await expect(page.locator('.move-row')).toHaveCount(1);
  await expect(page.getByRole('button',{name:'Undo'})).toBeDisabled();
  await page.getByLabel('Difficulty').selectOption('hard');
  await page.reload();
  await expect(heading(page)).toHaveText('Black to move');
  await page.getByText('Game settings', {exact:true}).click();
  await expect(page.getByLabel('Difficulty')).toHaveValue('hard');
});

test('starting position renders both complete teams with distinct rooks', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto('/');
  await expect(heading(page)).toHaveText('White to move');
  await expect(page.locator('.piece')).toHaveCount(32);
  await expect(page.locator('.piece.white')).toHaveCount(16);
  await expect(page.locator('.piece:not(.white)')).toHaveCount(16);
  await expect(page.getByRole('button',{name:'a1 white rook',exact:true})).toContainText('♖');
  await expect(page.getByRole('button',{name:'a8 black rook',exact:true})).toContainText('♜');
  expect(errors).toEqual([]);
});

test('Stockfish availability refreshes after the service recovers', async ({ page }) => {
  await page.route('**/api/engine', route => route.fulfill({status:200,contentType:'application/json',body:'{"available":false}'}));
  await page.goto('/');
  await expect(heading(page)).toHaveText('White to move');
  await expect(page.locator('#opponent option[value="stockfish"]')).toHaveText('Stockfish (unavailable)');
  await page.unroute('**/api/engine');
  await page.getByText('Game settings', {exact:true}).click();
  await expect(page.locator('#opponent option[value="stockfish"]')).toBeEnabled();
});

test('kingside castling moves both king and rook by selecting the king destination', async ({ page }) => {
  await openGame(page,['e4','e5','Nf3','Nc6','Bc4','Nf6']);
  await page.getByRole('button',{name:'e1 white king',exact:true}).click();
  await expect(page.getByRole('button',{name:'g1 empty, legal destination',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'g1 empty, legal destination',exact:true}).click();
  await expect(page.getByRole('button',{name:'g1 white king',exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'f1 white rook',exact:true})).toBeVisible();
  await expect(page.locator('.move-row').last()).toContainText('O-O');
  await expect(heading(page)).toHaveText('Black to move');
});

test('queenside castling also accepts king then rook', async ({ page }) => {
  await openGame(page,['d4','d5','Nc3','Nc6','Bf4','Bf5','Qd2','Qd7']);
  await page.getByRole('button',{name:'e1 white king',exact:true}).click();
  await page.getByRole('button',{name:'a1 white rook',exact:true}).click();
  await expect(page.getByRole('button',{name:'c1 white king',exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'d1 white rook',exact:true})).toBeVisible();
  await expect(page.locator('.move-row').last()).toContainText('O-O-O');
  await expect(heading(page)).toHaveText('Black to move');
});

test('black can castle by notation and both rook and king move', async ({ page }) => {
  await openGame(page,['e4','e5','Nf3','Nc6','Bc4','Nf6','d3','Bc5','Nc3']);
  await play(page,'O-O');
  await expect(page.getByRole('button',{name:'g8 black king',exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'f8 black rook',exact:true})).toBeVisible();
  await expect(heading(page)).toHaveText('White to move');
});

test('castling stays blocked while pieces are in the way', async ({ page }) => {
  await page.goto('/');
  await expect(heading(page)).toHaveText('White to move');
  await page.getByRole('button',{name:'e1 white king',exact:true}).click();
  await page.getByRole('button',{name:'h1 white rook',exact:true}).click();
  await expect(page.getByRole('button',{name:'e1 white king',exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'h1 white rook',exact:true})).toBeVisible();
  await expect(page.locator('.move-row')).toHaveCount(0);
  await page.getByLabel('Or enter a move').fill('O-O');
  await page.getByRole('button',{name:'Play entered move'}).click();
  await expect(page.getByRole('alert')).toContainText('Illegal move');
});
