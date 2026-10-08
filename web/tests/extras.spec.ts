import {test,expect} from '@playwright/test';
const h=(p:any)=>p.getByRole('heading',{level:2});
async function start(p:any){await p.goto('/');await expect(h(p)).toHaveText('White to move');}
async function play(p:any,m:string){await p.getByLabel('Or enter a move').fill(m);await p.getByRole('button',{name:'Play entered move',exact:true}).click();}
test('drag sound explanation replay',async({page,context})=>{
 await start(page);
 const from=page.getByRole('button',{name:'e2 white pawn',exact:true}),to=page.getByRole('button',{name:'e4 empty',exact:true});
 const a=(await from.boundingBox())!,b=(await to.boundingBox())!;
 await page.mouse.move(a.x+a.width/2,a.y+a.height/2);await page.mouse.down();
 await page.mouse.move(b.x+b.width/2,b.y+b.height/2,{steps:5});
 await expect(page.locator('.drag-piece')).toBeVisible();await page.mouse.up();
 await expect(h(page)).toHaveText('Black to move');
 await page.getByText('Game settings',{exact:true}).click();await page.getByRole('button',{name:'Enable sounds',exact:true}).click();
 await page.getByText('Explore & share',{exact:true}).click();await page.getByRole('button',{name:'Explain this position',exact:true}).click();
 await expect(page.getByLabel('Suggested move arrow')).toBeVisible({timeout:15000});await expect(page.locator('.candidate')).toHaveCount(3);
 await page.getByRole('button',{name:'Share replay ↗',exact:true}).click();const url=await page.getByLabel('Share link').inputValue();
 const replay=await context.newPage();await replay.goto(url);await expect(h(replay)).toHaveText('Black to move');await expect(replay.getByLabel('Or enter a move')).toBeDisabled();
 await replay.getByRole('button',{name:'Previous position',exact:true}).click();await expect(h(replay)).toHaveText('White to move · Review');
 await page.reload();await page.getByText('Game settings',{exact:true}).click();await expect(page.getByRole('button',{name:'Mute sounds',exact:true})).toBeVisible();
});
test('daily puzzle hints and streak',async({page})=>{
 await start(page);await page.getByText('Game settings',{exact:true}).click();await page.getByRole('button',{name:'Daily puzzle ↗',exact:true}).click();
 await expect(page.getByRole('status')).toContainText('Find mate in one');await page.getByRole('button',{name:'Puzzle hint',exact:true}).click();
 const data=await(await page.request.get('/api/puzzle')).json();await expect(page.getByRole('status')).toContainText(data.hint);
 await play(page,data.id===0?'Re8#':'Qg7#');await expect(page.getByRole('status')).toContainText('Solved');await expect(page.getByRole('status')).toContainText('1 day streak');
 page.on('dialog',d=>d.accept());await page.getByRole('button',{name:'Daily puzzle ↗',exact:true}).click();await play(page,data.id===0?'Re8#':'Qg7#');await expect(page.getByRole('status')).toContainText('1 day streak');
});
test('friend invite turns spectator refresh resignation',async({page,browser,baseURL})=>{
 await start(page);await page.getByText('Game settings',{exact:true}).click();await page.getByLabel('Friend match clock').selectOption('180');await page.getByRole('button',{name:'Invite a friend ↗',exact:true}).click();
 await expect(page.getByText('You play white · Waiting for a friend',{exact:true})).toBeVisible();await expect(page.getByLabel('Or enter a move')).toBeDisabled();
 const url=page.url(),fc=await browser.newContext({baseURL}),friend=await fc.newPage();await friend.goto(url);await friend.getByRole('button',{name:'Join match',exact:true}).click();await expect(friend.getByText('You play black',{exact:true})).toBeVisible();
 await expect(page.getByLabel('Or enter a move')).toBeEnabled();await play(page,'e4');await expect(h(friend)).toHaveText('Black to move');await play(friend,'e5');await expect(h(page)).toHaveText('White to move');
 await friend.reload();await expect(friend.getByText('You play black',{exact:true})).toBeVisible();
 const sc=await browser.newContext({baseURL}),spectator=await sc.newPage();await spectator.goto(url);await expect(spectator.getByText('Watching this match',{exact:true})).toBeVisible();await expect(spectator.getByLabel('Or enter a move')).toBeDisabled();
 page.on('dialog',d=>d.accept());await page.getByRole('button',{name:'Resign',exact:true}).click();await expect(h(friend)).toHaveText('0-1 · resignation');await fc.close();await sc.close();
});
test('postgame analysis graph',async({page})=>{
 test.setTimeout(45000);
 await page.addInitScript(()=>localStorage.setItem('aaryan-chess-v1',JSON.stringify(['f3','e5','g4','Qh4#'])));await page.goto('/');await expect(h(page)).toHaveText('0-1 · checkmate');
 await page.getByText('Explore & share',{exact:true}).click();await page.getByRole('button',{name:'Analyse finished game',exact:true}).click();await expect(page.getByLabel('Game evaluation graph, positive favors White')).toBeVisible({timeout:15000});
 await expect(page.getByRole('button',{name:'Analyse finished game',exact:true})).toBeEnabled({timeout:30000});await expect(page.locator('.analysis-list .candidate').first()).toContainText('Ply');
});

test('selected squares retain board colors with distinct rounded outlines',async({page},testInfo)=>{
 await start(page);
 const whiteSquare=page.getByRole('button',{name:'e2 white pawn',exact:true});
 const orangeSquare=page.getByRole('button',{name:'d2 white pawn',exact:true});
 const style=(e:Element)=>({background:getComputedStyle(e).backgroundColor,shadow:getComputedStyle(e).boxShadow});
 const initialWhite=await whiteSquare.evaluate(style),initialOrange=await orangeSquare.evaluate(style);
 await whiteSquare.click();await expect(whiteSquare).toHaveAttribute('aria-pressed','true');
 const selectedWhite=await whiteSquare.evaluate(style);expect(selectedWhite.background).toBe(initialWhite.background);expect(selectedWhite.shadow).not.toBe(initialWhite.shadow);
 await page.screenshot({path:testInfo.outputPath('rounded-board-white-selection.png'),fullPage:true});
 await orangeSquare.click();await expect(orangeSquare).toHaveAttribute('aria-pressed','true');const selectedOrange=await orangeSquare.evaluate(style);expect(selectedOrange.background).toBe(initialOrange.background);expect(selectedOrange.shadow).not.toBe(initialOrange.shadow);
 await page.screenshot({path:testInfo.outputPath('rounded-board-orange-selection.png'),fullPage:true});
 expect(await page.locator('.board').evaluate(e=>parseFloat(getComputedStyle(e).borderRadius))).toBeGreaterThanOrEqual(20);
});
