import fs from "node:fs/promises";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const input = "D:/광고보고서/public_dashboard/outputs/pptx_rebuild_tmp/source.pptx";
const out = "D:/광고보고서/public_dashboard/outputs/pptx_rebuild_tmp/direct-test.png";
const deck = await PresentationFile.importPptx(await FileBlob.load(input));
const result = await deck.inspect({ kind: "slide,textbox,shape,chart,table,image,layout", maxChars: 50000 });
await fs.writeFile("D:/광고보고서/public_dashboard/outputs/pptx_rebuild_tmp/direct-inspect.ndjson", result.ndjson, "utf8");
const png = await deck.export({ slide: deck.slides.items[0], format: "png", scale: 1 });
await fs.writeFile(out, new Uint8Array(await png.arrayBuffer()));
console.log(`slides=${deck.slides.items.length}`);
