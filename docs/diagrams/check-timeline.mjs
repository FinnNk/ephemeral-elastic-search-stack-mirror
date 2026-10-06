// Reuse the pinned Archify browser; tall timelines intentionally scroll vertically.
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
const [checkout, html, preview, receiptPath] = process.argv.slice(2);
const {ChromeVisualBrowser, findChrome, VISUAL_CHECK_VIEWPORTS} = await import(
  pathToFileURL(path.resolve(checkout, 'archify/bin/visual-check.mjs')).href);
const executable = findChrome();
if (!executable) throw new Error('Chrome is required for timeline browser checks.');
const browser = new ChromeVisualBrowser(executable), results = [];
try {
  for (const viewport of VISUAL_CHECK_VIEWPORTS) for (const theme of ['light', 'dark']) {
    const metrics = await browser.inspect({artifactPath:path.resolve(html), ...viewport, theme});
    if (metrics.scrollWidth > metrics.innerWidth || !metrics.hasLegend
        || metrics.minimumProjectedNodeTextPx < 6 || metrics.dockStageIntersectionArea > 0
        || metrics.resolvedTheme !== theme) {
      throw new Error('Timeline layout check failed: ' + JSON.stringify(metrics));
    }
    results.push({...viewport, theme, ...metrics, verticalScrollingAllowed:true});
    if (viewport.width === 1440 && theme === 'light') {
      const session = await browser.sessionPromise;
      const image = await browser.cdp.send('Page.captureScreenshot', {
        format:'png', captureBeyondViewport:true,
        clip:{x:0,y:0,width:metrics.scrollWidth,height:metrics.scrollHeight,scale:1},
      }, session, 20000);
      fs.writeFileSync(preview, Buffer.from(image.data, 'base64'));
    }
  }
} finally { await browser.close(); }
fs.writeFileSync(receiptPath, JSON.stringify({ok:true,status:'pass',
  method:'Pinned Archify Chrome browser; full-page timeline',
  sha256:createHash('sha256').update(fs.readFileSync(html)).digest('hex'),
  scope:'Vertical scrolling is intentional. Horizontal overflow, unreadable text and dock overlap remain failures.',
  viewports:results}, null, 2)+'\n');
console.log('Timeline browser checks passed in both themes at four desktop sizes.');
