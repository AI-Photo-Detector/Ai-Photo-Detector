import { AnalysisResult } from "../App";
import { Card } from "./ui/card";
import { Badge } from "./ui/badge";
import { Progress } from "./ui/progress";
import { CheckCircle, AlertTriangle, XCircle, Calendar, FileText } from "lucide-react";
import { Button } from "./ui/button";

interface ResultsDashboardProps {
  results: AnalysisResult[];
  selectedResult: AnalysisResult;
  onSelectResult: (result: AnalysisResult) => void;
}

export function ResultsDashboard({ results, selectedResult, onSelectResult }: ResultsDashboardProps) {
  const getStatusIcon = (status: string) => {
    switch (status) {
      case "pass":
        return <CheckCircle className="w-4 h-4 text-emerald-500" />;
      case "warning":
        return <AlertTriangle className="w-4 h-4 text-amber-500" />;
      case "fail":
        return <XCircle className="w-4 h-4 text-rose-400" />;
      default:
        return null;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "pass":
        return "bg-emerald-100 text-emerald-700 border-emerald-200";
      case "warning":
        return "bg-amber-100 text-amber-700 border-amber-200";
      case "fail":
        return "bg-rose-100 text-rose-700 border-rose-200";
      default:
        return "bg-gray-100 text-gray-800 border-gray-200";
    }
  };

  return (
    <div className="space-y-6">
      {/* Main Result Card */}
      <Card className="p-6 shadow-md bg-white/70 backdrop-blur-sm border-[#8d70b3]/30">
        <div className="flex flex-col md:flex-row gap-6">
          <div className="md:w-1/2">
            <img
              src={selectedResult.imageUrl}
              alt={selectedResult.fileName}
              className="w-full h-64 object-cover rounded-lg border-2 border-[#8d70b3]/30 shadow-sm"
            />
          </div>
          <div className="md:w-1/2 space-y-4">
            <div>
              <h3 className="text-gray-900 mb-1">{selectedResult.fileName}</h3>
              <div className="flex items-center gap-2 text-sm text-gray-500">
                <Calendar className="w-4 h-4 text-[#655080]" />
                {selectedResult.uploadDate.toLocaleString()}
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Detection Result</span>
                <Badge
                  variant={selectedResult.isAIGenerated ? "destructive" : "default"}
                  className="text-sm"
                >
                  {selectedResult.isAIGenerated ? "AI Generated" : "Real Photo"}
                </Badge>
              </div>
              <div>
                <div className="flex items-center justify-between text-sm mb-1">
                  <span className="text-gray-600">Confidence Score</span>
                  <span className="text-gray-900">{selectedResult.confidence.toFixed(1)}%</span>
                </div>
                <Progress value={selectedResult.confidence} className="h-2" />
              </div>
            </div>

            <div className="pt-4 border-t border-[#8d70b3]/30">
              <p className="text-sm text-gray-600 mb-2">File Information</p>
              <div className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">Size:</span>
                  <span className="text-gray-900">
                    {(selectedResult.fileSize / 1024 / 1024).toFixed(2)} MB
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Format:</span>
                  <span className="text-gray-900">
                    {selectedResult.fileName.split(".").pop()?.toUpperCase()}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </Card>

      {/* Detection Indicators */}
      <Card className="p-6 shadow-md bg-white/70 backdrop-blur-sm border-[#8d70b3]/30">
        <h3 className="text-gray-900 mb-4">Detection Indicators</h3>
        <div className="space-y-4">
          {selectedResult.indicators.map((indicator, index) => (
            <div key={index} className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {getStatusIcon(indicator.status)}
                  <span className="text-sm text-gray-900">{indicator.label}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-600">{indicator.value.toFixed(1)}%</span>
                  <Badge variant="outline" className={`text-xs border ${getStatusColor(indicator.status)}`}>
                    {indicator.status}
                  </Badge>
                </div>
              </div>
              <Progress value={indicator.value} className="h-1.5" />
            </div>
          ))}
        </div>
      </Card>

      {/* Summary */}
      <Card className="p-6 bg-gradient-to-br from-[#b690e6]/60 via-[#a280cc]/40 to-[#8d70b3]/60 border-[#8d70b3] shadow-md">
        <h3 className="text-gray-900 mb-2">Analysis Summary</h3>
        <p className="text-gray-700 text-sm leading-relaxed">
          Based on our advanced AI detection algorithms, this image has been analyzed across
          multiple indicators including pixel consistency, noise patterns, edge detection, and
          color distribution. The overall confidence score of{" "}
          <span className="font-medium">{selectedResult.confidence.toFixed(1)}%</span> indicates
          that this image is{" "}
          <span className="font-medium">
            {selectedResult.isAIGenerated ? "likely AI-generated" : "likely a real photograph"}
          </span>
          .
        </p>
      </Card>
    </div>
  );
}