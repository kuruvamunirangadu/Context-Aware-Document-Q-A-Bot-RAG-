import * as pdfjsLib from 'pdfjs-dist';
import pdfWorkerUrl from 'pdfjs-dist/build/pdf.worker.mjs?url';
import type { TextItem } from 'pdfjs-dist/types/src/display/api.js';

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

const normalizeExtractedText = (text: string): string =>
  text
    .replace(/\r\n?/g, '\n')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();

export const extractPdfText = async (file: File): Promise<string> => {
  const data = await file.arrayBuffer();
  const document = await pdfjsLib.getDocument({ data }).promise;
  const pages: string[] = [];

  for (let pageNumber = 1; pageNumber <= document.numPages; pageNumber += 1) {
    const page = await document.getPage(pageNumber);
    const textContent = await page.getTextContent();
    const pageText = textContent.items
      .filter((item): item is TextItem => 'str' in item)
      .map((item) => item.str)
      .join(' ');

    if (pageText.trim()) {
      pages.push(`Page ${pageNumber}\n${pageText}`);
    }
  }

  await document.destroy();

  const text = normalizeExtractedText(pages.join('\n\n'));
  if (!text) {
    throw new Error('No selectable text was found in this PDF. It may be scanned or image-only.');
  }

  return text;
};

export const fileNameWithoutExtension = (filename: string): string => filename.replace(/\.[^/.]+$/, '');
