import { Card } from "./ui/card";
import { Upload, FileText, Download, CheckCircle } from "lucide-react";

export function HowToGuide() {
  const steps = [
    {
      icon: Upload,
      title: "Upload Your Images",
      description: "Navigate to the Upload tab and either drag and drop your images or click 'Choose Photo' to select them from your device. You can upload multiple images at once.",
      tips: [
        "Supported formats: JPG, PNG, WEBP",
        "Maximum file size: 10MB per image",
        "You can upload multiple images simultaneously"
      ]
    },
    {
      icon: CheckCircle,
      title: "Analyze Your Photos",
      description: "Once you've selected your images, click the 'Analyze Images' button. The detector returns an overall AI model score and supporting evidence checks.",
      tips: [
        "Analysis typically takes 2-3 seconds per image",
        "Forensic checks look for metadata, edit hotspots, clone regions, and compression or texture artifacts",
        "Each image receives a confidence score from 0-100%"
      ]
    },
    {
      icon: FileText,
      title: "Review Results",
      description: "Switch to the Results tab to see detailed analysis for your uploaded image. The report separates the AI model score from supporting heuristic checks.",
      tips: [
        "View confidence scores and detection status",
        "Review provenance, watermark, and manipulation evidence separately",
        "Treat colored maps as supporting signals, not proof"
      ]
    },
    {
      icon: Download,
      title: "Export PDF Report",
      description: "Click the 'Export PDF Report' button to download a comprehensive PDF document containing the analysis result, model score, and supporting evidence checks.",
      tips: [
        "PDF includes forensic evidence summaries and maps",
        "Contains image preview and file information",
        "Includes a clear disclaimer for documentation and sharing"
      ]
    }
  ];

  return (
    <div className="space-y-6">
      <Card className="guide-card p-6 shadow-md bg-white/70 backdrop-blur-sm border-[#8d70b3]/30">
        <h2 className="text-gray-900 mb-2">How to Use AI Photo Detector</h2>
        <p className="text-gray-600">
          Follow these simple steps to detect AI-generated images with confidence
        </p>
      </Card>

      <div className="space-y-6">
        {steps.map((step, index) => {
          const Icon = step.icon;
          return (
            <Card key={index} className="guide-card p-6 shadow-md bg-white/70 backdrop-blur-sm border-[#8d70b3]/30">
              <div className="flex gap-4">
                <div className="flex-shrink-0">
                  <div className="w-12 h-12 bg-gradient-to-br from-[#8d70b3] to-[#655080] rounded-lg flex items-center justify-center shadow-md">
                    <Icon className="w-6 h-6 text-white" />
                  </div>
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <span className="text-sm text-[#655080]">Step {index + 1}</span>
                    <h3 className="text-gray-900">{step.title}</h3>
                  </div>
                  <p className="text-gray-700 mb-4">{step.description}</p>
                  <div className="guide-tips-panel bg-gradient-to-br from-[#f5f0ff] to-[#b690e6]/50 rounded-lg p-4 border border-[#8d70b3]/30">
                    <p className="text-sm text-gray-900 mb-2">Tips:</p>
                    <ul className="space-y-1">
                      {step.tips.map((tip, tipIndex) => (
                        <li key={tipIndex} className="text-sm text-gray-700 flex items-start gap-2">
                          <span className="text-[#655080] mt-0.5">-</span>
                          <span>{tip}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      <Card className="guide-results-card p-6 bg-gradient-to-br from-[#b690e6]/60 via-[#a280cc]/40 to-[#8d70b3]/60 border-[#8d70b3] shadow-md">
        <h3 className="text-gray-900 mb-2">Understanding Results</h3>
        <div className="space-y-3 text-sm">
          <div>
            <p className="text-gray-900 mb-1">Confidence Score</p>
            <p className="text-gray-700">
              A percentage showing the detector verdict confidence. It is an estimate, not a guarantee.
            </p>
          </div>
          <div>
            <p className="text-gray-900 mb-1">Supporting Evidence Checks</p>
            <p className="text-gray-700">
              Separate checks look for AI provenance metadata, watermark markers, edit hotspots,
              clone regions, compression mismatches, and local texture inconsistencies. Some checks are heuristic signals.
            </p>
          </div>
          <div>
            <p className="text-gray-900 mb-1">Status Badges</p>
            <p className="text-gray-700">
              Each indicator is marked as Pass (green), Warning (yellow), or Fail (red) to help you
              understand which aspects suggest AI generation.
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}
