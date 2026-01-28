import { jsPDF } from "jspdf";
import { AnalysisResult } from "../App";

export function exportToPDF(result: AnalysisResult) {
  const pdf = new jsPDF();
  const pageWidth = pdf.internal.pageSize.getWidth();
  const margin = 20;
  let yPosition = 20;

  // Title
  pdf.setFontSize(20);
  pdf.setTextColor(31, 41, 55);
  pdf.text("AI Photo Detection Report", margin, yPosition);
  
  yPosition += 15;
  
  // Horizontal line
  pdf.setDrawColor(229, 231, 235);
  pdf.setLineWidth(0.5);
  pdf.line(margin, yPosition, pageWidth - margin, yPosition);
  
  yPosition += 15;

  // File Information
  pdf.setFontSize(14);
  pdf.setTextColor(31, 41, 55);
  pdf.text("File Information", margin, yPosition);
  
  yPosition += 10;
  
  pdf.setFontSize(10);
  pdf.setTextColor(75, 85, 99);
  pdf.text(`File Name: ${result.fileName}`, margin, yPosition);
  yPosition += 7;
  pdf.text(`Upload Date: ${result.uploadDate.toLocaleString()}`, margin, yPosition);
  yPosition += 7;
  pdf.text(`File Size: ${(result.fileSize / 1024 / 1024).toFixed(2)} MB`, margin, yPosition);
  yPosition += 7;
  pdf.text(`Format: ${result.fileName.split(".").pop()?.toUpperCase()}`, margin, yPosition);
  
  yPosition += 15;

  // Detection Result
  pdf.setFontSize(14);
  pdf.setTextColor(31, 41, 55);
  pdf.text("Detection Result", margin, yPosition);
  
  yPosition += 10;
  
  // Result box
  const resultText = result.isAIGenerated ? "AI Generated" : "Real Photo";
  const resultColor = result.isAIGenerated ? [220, 38, 38] : [22, 163, 74];
  
  pdf.setFillColor(resultColor[0], resultColor[1], resultColor[2]);
  pdf.setTextColor(255, 255, 255);
  pdf.setFontSize(12);
  pdf.rect(margin, yPosition - 5, 60, 10, "F");
  pdf.text(resultText, margin + 30, yPosition + 2, { align: "center" });
  
  yPosition += 15;
  
  // Confidence Score
  pdf.setFontSize(10);
  pdf.setTextColor(75, 85, 99);
  pdf.text(`Confidence Score: ${result.confidence.toFixed(1)}%`, margin, yPosition);
  
  yPosition += 10;
  
  // Progress bar for confidence
  const barWidth = 100;
  const barHeight = 6;
  pdf.setFillColor(229, 231, 235);
  pdf.rect(margin, yPosition - 3, barWidth, barHeight, "F");
  pdf.setFillColor(59, 130, 246);
  pdf.rect(margin, yPosition - 3, (barWidth * result.confidence) / 100, barHeight, "F");
  
  yPosition += 15;

  // Detection Indicators
  pdf.setFontSize(14);
  pdf.setTextColor(31, 41, 55);
  pdf.text("Detection Indicators", margin, yPosition);
  
  yPosition += 10;

  result.indicators.forEach((indicator, index) => {
    if (yPosition > 250) {
      pdf.addPage();
      yPosition = 20;
    }
    
    pdf.setFontSize(10);
    pdf.setTextColor(31, 41, 55);
    pdf.text(indicator.label, margin, yPosition);
    
    // Status badge
    let statusColor;
    let statusText;
    switch (indicator.status) {
      case "pass":
        statusColor = [22, 163, 74];
        statusText = "PASS";
        break;
      case "warning":
        statusColor = [234, 179, 8];
        statusText = "WARNING";
        break;
      case "fail":
        statusColor = [220, 38, 38];
        statusText = "FAIL";
        break;
      default:
        statusColor = [156, 163, 175];
        statusText = "N/A";
    }
    
    pdf.setFillColor(statusColor[0], statusColor[1], statusColor[2]);
    pdf.setTextColor(255, 255, 255);
    pdf.setFontSize(8);
    pdf.rect(margin + 80, yPosition - 4, 20, 6, "F");
    pdf.text(statusText, margin + 90, yPosition, { align: "center" });
    
    pdf.setTextColor(75, 85, 99);
    pdf.setFontSize(10);
    pdf.text(`${indicator.value.toFixed(1)}%`, margin + 105, yPosition);
    
    yPosition += 5;
    
    // Progress bar
    const indicatorBarWidth = 80;
    const indicatorBarHeight = 4;
    pdf.setFillColor(229, 231, 235);
    pdf.rect(margin, yPosition - 2, indicatorBarWidth, indicatorBarHeight, "F");
    pdf.setFillColor(59, 130, 246);
    pdf.rect(margin, yPosition - 2, (indicatorBarWidth * indicator.value) / 100, indicatorBarHeight, "F");
    
    yPosition += 10;
  });

  yPosition += 10;

  // Summary
  if (yPosition > 220) {
    pdf.addPage();
    yPosition = 20;
  }
  
  pdf.setFontSize(14);
  pdf.setTextColor(31, 41, 55);
  pdf.text("Analysis Summary", margin, yPosition);
  
  yPosition += 10;
  
  pdf.setFontSize(10);
  pdf.setTextColor(75, 85, 99);
  const summaryText = `Based on advanced AI detection algorithms, this image has been analyzed across multiple indicators including pixel consistency, noise patterns, edge detection, and color distribution. The overall confidence score of ${result.confidence.toFixed(1)}% indicates that this image is ${result.isAIGenerated ? "likely AI-generated" : "likely a real photograph"}.`;
  
  const splitText = pdf.splitTextToSize(summaryText, pageWidth - 2 * margin);
  pdf.text(splitText, margin, yPosition);
  
  yPosition += splitText.length * 7 + 10;

  // Footer
  pdf.setFontSize(8);
  pdf.setTextColor(156, 163, 175);
  pdf.text(
    `Generated on ${new Date().toLocaleString()} | AI Photo Detector`,
    pageWidth / 2,
    pdf.internal.pageSize.getHeight() - 10,
    { align: "center" }
  );

  // Save PDF
  pdf.save(`AI_Detection_Report_${result.fileName.split(".")[0]}.pdf`);
}
