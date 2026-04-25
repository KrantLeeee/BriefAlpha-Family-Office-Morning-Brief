"use client";

/**
 * react-pdf based viewer with bbox highlight overlay.
 *
 * MVP scope: render `pageNumber` of the supplied URL and overlay a single
 * highlight rectangle scaled into page coordinates. The full bbox→page
 * mapping with multi-rectangle highlights and `original PDF deleted` state
 * lives in section 14 (research-upload). Until uploads land in this slice,
 * the component is exported but only mounted when a file URL is supplied.
 */
import { useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";

if (typeof window !== "undefined") {
  pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.js`;
}

interface Props {
  fileUrl: string;
  pageNumber: number;
  bbox?: { x0: number; y0: number; x1: number; y1: number };
  pageDeleted?: boolean;
}

export function ResearchPdfViewer({ fileUrl, pageNumber, bbox, pageDeleted }: Props) {
  const [pageWidth, setPageWidth] = useState<number | null>(null);
  const [pageHeight, setPageHeight] = useState<number | null>(null);

  if (pageDeleted) {
    return (
      <div className="rounded-card border border-line bg-surface p-4">
        <p className="font-sans text-[13px] text-ink-500">原 PDF 已删除（≥ 7 天）。可重新上传后再追溯。</p>
      </div>
    );
  }

  return (
    <div className="relative">
      <Document file={fileUrl}>
        <Page
          pageNumber={pageNumber}
          onLoadSuccess={({ width, height }) => {
            setPageWidth(width);
            setPageHeight(height);
          }}
          renderAnnotationLayer={false}
          renderTextLayer={false}
        />
      </Document>
      {bbox && pageWidth && pageHeight && (
        <span
          aria-label="证据位置"
          className="pointer-events-none absolute border-2 border-orange-600 bg-orange-600/10"
          style={{
            left: `${(bbox.x0 / pageWidth) * 100}%`,
            top: `${(bbox.y0 / pageHeight) * 100}%`,
            width: `${((bbox.x1 - bbox.x0) / pageWidth) * 100}%`,
            height: `${((bbox.y1 - bbox.y0) / pageHeight) * 100}%`,
          }}
        />
      )}
    </div>
  );
}
