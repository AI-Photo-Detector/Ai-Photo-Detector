import { jsPDF } from "jspdf";
import { AnalysisResult } from "../App";

type PdfColor = [number, number, number];

const PAGE_MARGIN = 20;
const LINE_HEIGHT = 6;

function ensureSpace(pdf: jsPDF, yPosition: number, requiredHeight: number) {
  const pageHeight = pdf.internal.pageSize.getHeight();
  if (yPosition + requiredHeight <= pageHeight - PAGE_MARGIN) {
    return yPosition;
  }

  pdf.addPage();
  return PAGE_MARGIN;
}

function writeWrappedText(
  pdf: jsPDF,
  text: string,
  x: number,
  yPosition: number,
  maxWidth: number,
  lineHeight = LINE_HEIGHT
) {
  const lines = pdf.splitTextToSize(text, maxWidth) as string[];
  pdf.text(lines, x, yPosition);
  return yPosition + lines.length * lineHeight;
}

function sectionTitle(pdf: jsPDF, title: string, yPosition: number) {
  yPosition = ensureSpace(pdf, yPosition, 18);
  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(14);
  pdf.setTextColor(31, 41, 55);
  pdf.text(title, PAGE_MARGIN, yPosition);
  pdf.setFont("helvetica", "normal");
  return yPosition + 10;
}

function addFooter(pdf: jsPDF) {
  const pageCount = pdf.getNumberOfPages();
  const pageWidth = pdf.internal.pageSize.getWidth();
  const pageHeight = pdf.internal.pageSize.getHeight();

  for (let page = 1; page <= pageCount; page += 1) {
    pdf.setPage(page);
    pdf.setFontSize(8);
    pdf.setTextColor(156, 163, 175);
    pdf.text(
      `Generated on ${new Date().toLocaleString()} | AI Photo Detector | Page ${page} of ${pageCount}`,
      pageWidth / 2,
      pageHeight - 10,
      { align: "center" }
    );
  }
}

function safeFileBaseName(fileName: string) {
  return fileName.replace(/\.[^/.]+$/, "").replace(/[^\w-]+/g, "_") || "image";
}

function writeOfficialReportLine(pdf: jsPDF, line: string, yPosition: number, pageWidth: number) {
  const trimmed = line.trim();
  const contentWidth = pageWidth - PAGE_MARGIN * 2;

  if (trimmed === "") {
    return yPosition + 3.5;
  }

  yPosition = ensureSpace(pdf, yPosition, 12);

  if (/^=+$/.test(trimmed) || /^-+$/.test(trimmed)) {
    pdf.setDrawColor(148, 163, 184);
    pdf.setLineWidth(/^=+$/.test(trimmed) ? 0.55 : 0.35);
    pdf.line(PAGE_MARGIN, yPosition - 3, pageWidth - PAGE_MARGIN, yPosition - 3);
    return yPosition + 2.5;
  }

  const isMainTitle = trimmed === "FAKE PHOTO DETECTOR - ANALYSIS REPORT";
  const isSectionTitle =
    trimmed === trimmed.toUpperCase() &&
    trimmed.length <= 40 &&
    !trimmed.startsWith("-") &&
    !trimmed.includes(":");

  if (isMainTitle) {
    pdf.setFont("times", "bold");
    pdf.setFontSize(19);
    pdf.setTextColor(17, 24, 39);
    return writeWrappedText(pdf, trimmed, PAGE_MARGIN, yPosition, contentWidth, 8.5) + 1.5;
  }

  if (isSectionTitle) {
    yPosition = ensureSpace(pdf, yPosition, 16);
    pdf.setFont("times", "bold");
    pdf.setFontSize(13.5);
    pdf.setTextColor(17, 24, 39);
    return writeWrappedText(pdf, trimmed, PAGE_MARGIN, yPosition, contentWidth, 7) + 0.5;
  }

  if (trimmed.startsWith("Test Name:")) {
    yPosition = ensureSpace(pdf, yPosition, 18);
    pdf.setFont("times", "bold");
    pdf.setFontSize(11);
    pdf.setTextColor(30, 41, 59);
    return writeWrappedText(pdf, trimmed, PAGE_MARGIN, yPosition, contentWidth, 5.5) + 1;
  }

  const isFieldLine = /^[A-Za-z][A-Za-z /]+:/.test(trimmed);
  const bodyFont = isFieldLine ? "courier" : "times";
  pdf.setFont(bodyFont, "normal");
  pdf.setFontSize(isFieldLine ? 9.2 : 10.3);
  pdf.setTextColor(isFieldLine ? 51 : 55, isFieldLine ? 65 : 65, isFieldLine ? 85 : 81);
  return writeWrappedText(pdf, line, PAGE_MARGIN, yPosition, contentWidth, isFieldLine ? 4.8 : 5.4) + 0.8;
}

function exportOfficialReportPDF(result: AnalysisResult, officialReport: string) {
  const pdf = new jsPDF();
  const pageWidth = pdf.internal.pageSize.getWidth();
  let yPosition = PAGE_MARGIN;
  const reportLines = officialReport.split(/\r?\n/);

  pdf.setFillColor(248, 250, 252);
  pdf.rect(0, 0, pageWidth, 30, "F");
  pdf.setDrawColor(100, 116, 139);
  pdf.setLineWidth(0.6);
  pdf.line(PAGE_MARGIN, 30, pageWidth - PAGE_MARGIN, 30);
  pdf.setFont("times", "bold");
  pdf.setFontSize(10);
  pdf.setTextColor(71, 85, 105);
  pdf.text("AI PHOTO DETECTOR", PAGE_MARGIN, 13);
  pdf.setFont("times", "normal");
  pdf.text("Official Analysis Report", PAGE_MARGIN, 20);
  yPosition = 40;

  reportLines.forEach((line) => {
    yPosition = writeOfficialReportLine(pdf, line, yPosition, pageWidth);
  });

  yPosition = ensureSpace(pdf, yPosition + 4, 24);
  yPosition = sectionTitle(pdf, "Disclaimer", yPosition);
  pdf.setFontSize(10);
  pdf.setTextColor(75, 85, 99);
  writeWrappedText(
    pdf,
    "This report is an estimate. Model scores and forensic checks are supporting signals, not proof. Use it alongside source verification, image provenance, and human review.",
    PAGE_MARGIN,
    yPosition,
    pageWidth - PAGE_MARGIN * 2
  );

  addFooter(pdf);
  pdf.save(`AI_Detection_Report_${safeFileBaseName(result.fileName)}.pdf`);
}

function formatProvider(provider?: string | null) {
  if (!provider) return "Unknown";
  if (provider === "bitmind_api") return "BitMind API";
  if (provider === "heuristic_fallback") return "Fallback Heuristic";
  if (provider === "configured_model") return "Configured Model";
  return provider.replace(/_/g, " ");
}

function displayForensicName(testName: string) {
  const normalized = testName.toLowerCase();
  if (normalized.includes("frequency fingerprint")) {
    return "Frequency Heuristic Check";
  }
  if (normalized.includes("diffusion") || normalized.includes("reconstruction")) {
    return "Reconstruction Proxy Check";
  }
  if (normalized.includes("vlm") || normalized.includes("visual review")) {
    return "VLM Visual Artifact Review";
  }
  if (normalized.includes("semantic")) {
    return "Structure Heuristic Check";
  }
  return testName;
}

function writeKeyValue(
  pdf: jsPDF,
  label: string,
  value: string,
  x: number,
  yPosition: number,
  maxWidth: number
) {
  pdf.setFont("helvetica", "bold");
  pdf.setTextColor(31, 41, 55);
  pdf.text(`${label}:`, x, yPosition);
  pdf.setFont("helvetica", "normal");
  pdf.setTextColor(75, 85, 99);
  return writeWrappedText(pdf, value, x + 38, yPosition, maxWidth - 38, 5);
}

export function exportToPDF(result: AnalysisResult) {
  if (result.officialReport?.trim()) {
    exportOfficialReportPDF(result, result.officialReport);
    return;
  }

  const pdf = new jsPDF();
  const pageWidth = pdf.internal.pageSize.getWidth();
  let yPosition = PAGE_MARGIN;

  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(20);
  pdf.setTextColor(31, 41, 55);
  pdf.text("AI Photo Detection Report", PAGE_MARGIN, yPosition);

  pdf.setFont("helvetica", "normal");
  pdf.setFontSize(9);
  pdf.setTextColor(107, 114, 128);
  pdf.text("Official summary generated by AI Photo Detector", PAGE_MARGIN, yPosition + 7);

  yPosition += 16;
  pdf.setDrawColor(229, 231, 235);
  pdf.setLineWidth(0.5);
  pdf.line(PAGE_MARGIN, yPosition, pageWidth - PAGE_MARGIN, yPosition);
  yPosition += 12;

  const resultText = result.isAIGenerated ? "AI Generated" : "Low AI Signal";
  const resultColor: PdfColor = result.isAIGenerated ? [220, 38, 38] : [22, 163, 74];
  const forensicTests = result.forensic_tests ?? [];
  const suspiciousCount = forensicTests.filter((test) => test.verdict === "suspicious").length;
  const inconclusiveCount = forensicTests.filter((test) => test.verdict === "inconclusive").length;
  const cleanCount = forensicTests.filter((test) => test.verdict === "clean").length;

  pdf.setFillColor(248, 250, 252);
  pdf.setDrawColor(226, 232, 240);
  pdf.roundedRect(PAGE_MARGIN, yPosition, pageWidth - PAGE_MARGIN * 2, 48, 3, 3, "FD");

  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(11);
  pdf.setTextColor(31, 41, 55);
  pdf.text("Verdict", PAGE_MARGIN + 8, yPosition + 11);

  pdf.setFillColor(...resultColor);
  pdf.setTextColor(255, 255, 255);
  pdf.setFontSize(12);
  pdf.roundedRect(PAGE_MARGIN + 8, yPosition + 16, 62, 11, 2, 2, "F");
  pdf.text(resultText, PAGE_MARGIN + 39, yPosition + 23.5, { align: "center" });

  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(10);
  pdf.setTextColor(31, 41, 55);
  pdf.text("Confidence", PAGE_MARGIN + 84, yPosition + 11);
  pdf.setTextColor(75, 85, 99);
  pdf.text(`${result.confidence.toFixed(1)}% detector verdict confidence`, PAGE_MARGIN + 84, yPosition + 22);

  const barWidth = pageWidth - PAGE_MARGIN * 2 - 92;
  const barHeight = 6;
  pdf.setFillColor(229, 231, 235);
  pdf.roundedRect(PAGE_MARGIN + 84, yPosition + 30, barWidth, barHeight, 2, 2, "F");
  pdf.setFillColor(141, 112, 179);
  pdf.roundedRect(PAGE_MARGIN + 84, yPosition + 30, (barWidth * result.confidence) / 100, barHeight, 2, 2, "F");
  yPosition += 62;

  yPosition = sectionTitle(pdf, "File Information", yPosition);
  pdf.setFontSize(10);
  yPosition = writeKeyValue(pdf, "File Name", result.fileName, PAGE_MARGIN, yPosition, pageWidth - PAGE_MARGIN * 2) + 2;
  yPosition = writeKeyValue(pdf, "Upload Date", result.uploadDate.toLocaleString(), PAGE_MARGIN, yPosition, pageWidth - PAGE_MARGIN * 2) + 2;
  yPosition = writeKeyValue(pdf, "File Size", `${(result.fileSize / 1024 / 1024).toFixed(2)} MB`, PAGE_MARGIN, yPosition, pageWidth - PAGE_MARGIN * 2) + 2;
  yPosition = writeKeyValue(pdf, "Format", result.fileName.split(".").pop()?.toUpperCase() ?? "UNKNOWN", PAGE_MARGIN, yPosition, pageWidth - PAGE_MARGIN * 2) + 8;

  yPosition = sectionTitle(pdf, "Evidence Summary", yPosition);
  pdf.setFontSize(10);
  pdf.setTextColor(75, 85, 99);
  yPosition = writeWrappedText(
    pdf,
    `Reviewed ${forensicTests.length} supporting evidence checks: ${suspiciousCount} suspicious, ${inconclusiveCount} inconclusive, and ${cleanCount} low-signal/clean. These checks support the model score but do not prove image origin on their own.`,
    PAGE_MARGIN,
    yPosition,
    pageWidth - PAGE_MARGIN * 2,
    5
  ) + 7;

  if (result.modelEvidence) {
    yPosition = sectionTitle(pdf, "Model Evidence", yPosition);
    pdf.setFontSize(10);
    pdf.setTextColor(75, 85, 99);
    pdf.text(`Provider: ${formatProvider(result.modelEvidence.provider)}`, PAGE_MARGIN, yPosition);
    yPosition += 7;
    pdf.text(`Raw AI Probability: ${result.modelEvidence.rawAiProbability.toFixed(1)}%`, PAGE_MARGIN, yPosition);
    yPosition += 7;
    pdf.text(`Provider Verdict: ${result.modelEvidence.providerVerdict ?? "Not supplied"}`, PAGE_MARGIN, yPosition);
    yPosition += 7;
    pdf.text(`Threshold: ${result.modelEvidence.threshold.toFixed(1)}%`, PAGE_MARGIN, yPosition);
    yPosition += 7;
    pdf.text(`Fallback Used: ${result.modelEvidence.usedFallback ? "Yes" : "No"}`, PAGE_MARGIN, yPosition);
    yPosition += 9;
    yPosition = writeWrappedText(
      pdf,
      result.modelEvidence.explanation,
      PAGE_MARGIN,
      yPosition,
      pageWidth - PAGE_MARGIN * 2,
      5
    ) + 5;
  }

  if (result.reliability) {
    yPosition = sectionTitle(pdf, "Result Reliability", yPosition);
    pdf.setFontSize(10);
    pdf.setTextColor(75, 85, 99);
    pdf.text(`${result.reliability.label}: ${result.reliability.score.toFixed(1)}%`, PAGE_MARGIN, yPosition);
    yPosition += 8;
    yPosition = writeWrappedText(
      pdf,
      result.reliability.explanation,
      PAGE_MARGIN,
      yPosition,
      pageWidth - PAGE_MARGIN * 2,
      5
    ) + 4;
    result.reliability.factors.slice(0, 4).forEach((factor) => {
      yPosition = ensureSpace(pdf, yPosition, 8);
      pdf.text(`- ${factor}`, PAGE_MARGIN, yPosition);
      yPosition += 6;
    });
    yPosition += 5;
  }

  if (result.robustness) {
    yPosition = sectionTitle(pdf, "Robustness / Stability Check", yPosition);
    pdf.setFontSize(10);
    pdf.setTextColor(75, 85, 99);
    pdf.text(`Status: ${result.robustness.label}`, PAGE_MARGIN, yPosition);
    yPosition += 7;
    pdf.text(`Consistency Index: ${(result.robustness.score * 100).toFixed(0)}/100`, PAGE_MARGIN, yPosition);
    yPosition += 7;
    if (typeof result.robustness.spread === "number") {
      pdf.text(`Raw AI Score Spread: ${result.robustness.spread.toFixed(1)}%`, PAGE_MARGIN, yPosition);
      yPosition += 7;
    }
    yPosition = writeWrappedText(
      pdf,
      result.robustness.explanation,
      PAGE_MARGIN,
      yPosition,
      pageWidth - PAGE_MARGIN * 2,
      5
    ) + 5;
  }

  if (result.forensic_tests?.length) {
    yPosition = sectionTitle(pdf, "Forensic Evidence", yPosition);

    result.forensic_tests.forEach((test) => {
      yPosition = ensureSpace(pdf, yPosition, 30);
      const details = test.details || {};
      const explanation =
        typeof details.explanation === "string" ? details.explanation : null;

      pdf.setFont("helvetica", "bold");
      pdf.setFontSize(11);
      pdf.setTextColor(31, 41, 55);
      pdf.text(displayForensicName(test.test_name), PAGE_MARGIN, yPosition);

      pdf.setFont("helvetica", "normal");
      pdf.setFontSize(10);
      pdf.setTextColor(75, 85, 99);
      pdf.text(
        `Verdict: ${test.verdict} | Signal: ${(test.score * 100).toFixed(1)}% | Test confidence: ${(test.confidence * 100).toFixed(1)}%`,
        PAGE_MARGIN,
        yPosition + 7
      );
      yPosition += 14;

      if (explanation) {
        yPosition = writeWrappedText(
          pdf,
          explanation,
          PAGE_MARGIN,
          yPosition,
          pageWidth - PAGE_MARGIN * 2,
          5
        ) + 5;
      }
    });
  }

  yPosition = sectionTitle(pdf, "Analysis Summary", yPosition);
  pdf.setFontSize(10);
  pdf.setTextColor(75, 85, 99);
  const summaryText = result.userSummary?.Summary
    ? `${result.userSummary.Summary} ${result.userSummary["Forensic Insight"]}`
    : result.isAIGenerated
      ? "The model score and supporting evidence checks suggest this image is likely AI-generated. Forensic maps highlight edit, clone, compression, or noise evidence when available. These results are assistive signals, not proof on their own."
      : "The model did not strongly flag this image as AI-generated. Clean forensic checks do not prove camera origin, and AI generation is still possible when metadata or watermarks are absent.";
  yPosition = writeWrappedText(
    pdf,
    summaryText,
    PAGE_MARGIN,
    yPosition,
    pageWidth - PAGE_MARGIN * 2
  ) + 8;

  yPosition = sectionTitle(pdf, "Disclaimer", yPosition);
  pdf.setFontSize(10);
  pdf.setTextColor(75, 85, 99);
  writeWrappedText(
    pdf,
    "This result is an estimate. Model score and forensic checks are supporting signals, not proof. Use this report as one input alongside source verification, image provenance, and human review.",
    PAGE_MARGIN,
    yPosition,
    pageWidth - PAGE_MARGIN * 2
  );

  addFooter(pdf);
  pdf.save(`AI_Detection_Report_${safeFileBaseName(result.fileName)}.pdf`);
}
