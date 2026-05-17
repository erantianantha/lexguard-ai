import puppeteer from 'puppeteer';
(async () => {
  const browser = await puppeteer.launch();
  const page = await browser.newPage();
  page.on('console', msg => console.log('BROWSER LOG:', msg.text()));
  page.on('pageerror', err => console.log('BROWSER ERROR:', err.message));
  await page.goto('http://localhost:5173/');
  await new Promise(r => setTimeout(r, 2000));
  
  // Find the first document card and click it
  const cards = await page.$$('.document-card');
  if (cards.length > 0) {
    console.log(`Found ${cards.length} document cards. Clicking the first one...`);
    await cards[0].click();
    await new Promise(r => setTimeout(r, 10000)); // wait for analysis page to load
  } else {
    console.log("No document cards found.");
  }
  await browser.close();
})();
