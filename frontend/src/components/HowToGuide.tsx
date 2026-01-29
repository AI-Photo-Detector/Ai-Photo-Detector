import { Card } from "./ui/card";
import { Upload, FileText, Download, CheckCircle } from "lucide-react";

export function HowToGuide() {
  const steps = [
    {
      icon: Upload,
      title: "Upload Your Images",
      description: "Navigate to the Upload tab and either drag and drop your images or click 'Browse Files' to select them from your device. You can upload multiple images at once.",
      tips: [
        "Supported formats: JPG, PNG, WEBP, GIF",
        "Maximum file size: 10MB per image",
        "You can upload multiple images simultaneously"
      ]
    },
    {
      icon: CheckCircle,
      title: "Analyze Your Photos",
      description: "Once you've selected your images, click the 'Analyze Images' button. Our AI detection system will process each image and check multiple indicators to determine if it was AI-generated.",
      tips: [
        "Analysis typically takes 2-3 seconds per image",
        "The system checks pixel consistency, noise patterns, and more",
        "Each image receives a confidence score from 0-100%"
      ]
    },
    {
      icon: FileText,
      title: "Review Results",
      description: "Switch to the Results tab to see detailed analysis for your uploaded image. The report includes individual indicator scores and a comprehensive summary.",
      tips: [
        "View confidence scores and detection status",
        "Check individual indicators like edge detection and color distribution",
        "Read the detailed analysis summary"
      ]
    },
    {
      icon: Download,
      title: "Export PDF Report",
      description: "Click the 'Export PDF Report' button to download a comprehensive PDF document containing the analysis results, confidence scores, and all detection indicators.",
      tips: [
        "PDF includes all detection indicators and scores",
        "Contains image preview and file information",
        "Perfect for documentation and sharing results"
      ]
    }
  ];

  return (
    <div className="space-y-6">
      <Card className="p-6 shadow-md bg-white/70 backdrop-blur-sm border-[#8d70b3]/30">
        <h2 className="text-gray-900 mb-2">How to Use AI Photo Detector</h2>
        <p className="text-gray-600">
          Follow these simple steps to detect AI-generated images with confidence
        </p>
      </Card>

      <div className="space-y-6">
        {steps.map((step, index) => {
          const Icon = step.icon;
          return (
            <Card key={index} className="p-6 shadow-md bg-white/70 backdrop-blur-sm border-[#8d70b3]/30">
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
                  <div className="bg-gradient-to-br from-[#f5f0ff] to-[#b690e6]/50 rounded-lg p-4 border border-[#8d70b3]/30">
                    <p className="text-sm text-gray-900 mb-2">Tips:</p>
                    <ul className="space-y-1">
                      {step.tips.map((tip, tipIndex) => (
                        <li key={tipIndex} className="text-sm text-gray-700 flex items-start gap-2">
                          <span className="text-[#655080] mt-0.5">•</span>
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

      <Card className="p-6 bg-gradient-to-br from-[#b690e6]/60 via-[#a280cc]/40 to-[#8d70b3]/60 border-[#8d70b3] shadow-md">
        <h3 className="text-gray-900 mb-2">Understanding Results</h3>
        <div className="space-y-3 text-sm">
          <div>
            <p className="text-gray-900 mb-1">Confidence Score</p>
            <p className="text-gray-700">
              A percentage indicating how confident our AI is in its detection. Higher scores mean
              greater certainty.
            </p>
          </div>
          <div>
            <p className="text-gray-900 mb-1">Detection Indicators</p>
            <p className="text-gray-700">
              Individual tests that examine different aspects of the image, such as pixel patterns,
              noise characteristics, and edge consistency.
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