import { AnalysisResult } from "../App";
import type { ReactNode } from "react";
import { Card } from "./ui/card";
import { Badge } from "./ui/badge";
import { Progress } from "./ui/progress";
import {
  Activity,
  Calendar,
  CheckCircle,
  Gauge,
  Image as ImageIcon,
  Layers,
  Server,
  ShieldCheck,
  ShieldQuestion,
} from "lucide-react";
import ForensicTestCard from "./ForensicTestCard";
import { normalizeForensicTests } from "../utils/forensicNormalizer";

interface ResultsDashboardProps {
  results: AnalysisResult[];
  selectedResult: AnalysisResult;
  isDarkMode?: boolean;
}

const panelStyle = {
  borderRadius: "16px",
  border: "1px solid var(--app-panel-border, rgba(141, 112, 179, 0.3))",
  background: "var(--app-panel-bg, rgba(255, 255, 255, 0.78))",
  boxShadow: "var(--app-panel-shadow, 0 18px 42px rgba(61, 48, 77, 0.14))",
};

const mutedPanelStyle = {
  borderRadius: "14px",
  border: "1px solid var(--app-muted-panel-border, rgba(141, 112, 179, 0.24))",
  background: "var(--app-muted-panel-bg, rgba(245, 240, 255, 0.58))",
};

function formatFileSize(bytes: number) {
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

function MediaFrame({
  children,
  maxWidth = "620px",
}: {
  children: ReactNode;
  maxWidth?: string;
}) {
  return (
    <div
      className="border"
      style={{
        width: `min(100%, ${maxWidth})`,
        aspectRatio: "4 / 3",
        borderRadius: "14px",
        backgroundColor: "transparent",
        borderColor: "rgba(141, 112, 179, 0.18)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        overflow: "hidden",
      }}
    >
      {children}
    </div>
  );
}

function isProvenanceTest(testName: string) {
  const normalized = testName.toLowerCase();
  return normalized.includes("provenance") || normalized.includes("watermark");
}

function isAiSpecificEvidenceTest(testName: string) {
  const normalized = testName.toLowerCase();
  return (
    isProvenanceTest(testName) ||
    normalized.includes("frequency fingerprint") ||
    normalized.includes("diffusion") ||
    normalized.includes("reconstruction") ||
    normalized.includes("vlm") ||
    normalized.includes("visual review") ||
    normalized.includes("semantic")
  );
}

function labelForProvider(provider?: string | null) {
  if (!provider) return "Unknown";
  if (provider === "bitmind_api") return "BitMind API";
  if (provider === "heuristic_fallback") return "Fallback Heuristic";
  if (provider === "configured_model") return "Configured Model";
  return provider.replace(/_/g, " ");
}

function badgeClassForReliability(level?: string) {
  switch (level) {
    case "high":
      return "bg-emerald-100 text-emerald-700 border-emerald-200";
    case "medium":
      return "bg-sky-100 text-sky-700 border-sky-200";
    case "low":
      return "bg-amber-100 text-amber-700 border-amber-200";
    case "conflicting":
      return "bg-rose-100 text-rose-700 border-rose-200";
    default:
      return "bg-gray-100 text-gray-700 border-gray-200";
  }
}

function badgeClassForSignal(strength?: string) {
  switch (strength) {
    case "strong":
      return "bg-emerald-100 text-emerald-700 border-emerald-200";
    case "moderate":
      return "bg-sky-100 text-sky-700 border-sky-200";
    case "weak":
      return "bg-amber-100 text-amber-700 border-amber-200";
    default:
      return "bg-gray-100 text-gray-700 border-gray-200";
  }
}

function badgeClassForRobustness(status?: string) {
  switch (status) {
    case "stable":
      return "bg-emerald-100 text-emerald-700 border-emerald-200";
    case "mixed":
      return "bg-amber-100 text-amber-700 border-amber-200";
    case "unstable":
      return "bg-rose-100 text-rose-700 border-rose-200";
    default:
      return "bg-gray-100 text-gray-700 border-gray-200";
  }
}

function stabilityMeaning(status?: string) {
  switch (status) {
    case "stable":
      return "Stable";
    case "mixed":
      return "Mostly stable";
    case "unstable":
      return "Unstable";
    case "disabled":
      return "Not checked";
    default:
      return "Limited data";
  }
}

function variantBadgeClass(verdict: string) {
  return verdict.toLowerCase().includes("ai generated")
    ? "bg-rose-100 text-rose-700 border-rose-200"
    : "bg-emerald-100 text-emerald-700 border-emerald-200";
}

function variantVerdictLabel(verdict: string) {
  return verdict.toLowerCase().includes("ai generated") ? "AI" : "Low AI";
}

function hasVariantVerdictFlip(variants: { verdict: string }[]) {
  if (variants.length < 2) return false;
  const firstVerdict = variants[0].verdict;
  return variants.slice(1).some((variant) => variant.verdict !== firstVerdict);
}

function DetailRow({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="flex justify-between gap-3 text-xs">
      <span className="text-gray-500">{label}</span>
      <span className="text-gray-900 text-right" style={{ overflowWrap: "anywhere" }}>
        {value}
      </span>
    </div>
  );
}

export function ResultsDashboard({
  selectedResult,
  isDarkMode = false,
}: ResultsDashboardProps) {
  const forensicTests = normalizeForensicTests(selectedResult);
  const aiSpecificTests = forensicTests.filter((test) => isAiSpecificEvidenceTest(test.test_name));
  const manipulationTests = forensicTests.filter((test) => !isAiSpecificEvidenceTest(test.test_name));
  const evidenceCheckCount = forensicTests.length;
  const modelEvidence = selectedResult.modelEvidence;
  const reliability = selectedResult.reliability;
  const robustness = selectedResult.robustness;
  const userSummary = selectedResult.userSummary;
  const detectionLabel = selectedResult.isAIGenerated
    ? "AI Generated"
    : "Low AI Signal";
  const statTextColor = isDarkMode ? "#faf7ff" : "#1f2937";
  const statMutedColor = isDarkMode ? "#d8cbe8" : "#655080";
  const statIconColor = isDarkMode ? "#efe8f8" : "#655080";
  const statCards = [
    {
      label: "Detection",
      value: detectionLabel,
      detail: `${selectedResult.confidence.toFixed(1)}% confidence`,
      icon: CheckCircle,
    },
    {
      label: "Confidence",
      value: `${selectedResult.confidence.toFixed(1)}%`,
      detail: "detector verdict confidence",
      icon: Gauge,
    },
    {
      label: "Evidence Checks",
      value: String(evidenceCheckCount),
      detail: "forensic maps reviewed",
      icon: Layers,
    },
    {
      label: "File Size",
      value: formatFileSize(selectedResult.fileSize),
      detail: selectedResult.fileName,
      icon: ImageIcon,
    },
  ];

  return (
    <div
      style={{
        width: "min(100%, 1320px)",
        margin: "0 auto",
        display: "grid",
        gap: "1.25rem",
        fontSize: "0.95rem",
        lineHeight: 1.4,
      }}
    >
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))",
          gap: "1rem",
        }}
      >
        {statCards.map((item) => {
          const Icon = item.icon;
          return (
            <Card
              key={item.label}
              style={{
                ...panelStyle,
                minHeight: "108px",
                padding: "1rem",
                justifyContent: "space-between",
                gap: "0.75rem",
              }}
            >
              <div className="flex items-center justify-between gap-3">
                <span
                  style={{
                    color: statMutedColor,
                    fontSize: "0.82rem",
                    fontWeight: 700,
                  }}
                >
                  {item.label}
                </span>
                <Icon className="w-5 h-5" style={{ color: statIconColor }} />
              </div>
              <div>
                <p
                  style={{
                    color: statTextColor,
                    fontSize: item.value.length > 10 ? "1.2rem" : "1.45rem",
                    fontWeight: 700,
                    lineHeight: 1.1,
                    overflowWrap: "anywhere",
                  }}
                >
                  {item.value}
                </p>
                <p
                  style={{
                    color: statMutedColor,
                    fontSize: "0.84rem",
                    display: "-webkit-box",
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: "vertical",
                    overflow: "hidden",
                  }}
                >
                  {item.detail}
                </p>
              </div>
            </Card>
          );
        })}
      </div>

      <Card style={{ ...panelStyle, padding: "1rem 1.15rem" }}>
        <div className="flex items-start gap-3">
          <ShieldQuestion
            className="w-5 h-5"
            style={{ color: statIconColor, flexShrink: 0, marginTop: "0.1rem" }}
          />
          <div>
            <h3
              className="font-semibold text-gray-900"
              style={{ color: statTextColor, fontSize: "1rem" }}
            >
              What this means
            </h3>
            <p
              className="text-gray-600"
              style={{ color: statMutedColor, fontSize: "0.92rem", lineHeight: 1.45 }}
            >
              This result is an estimate. Model score and forensic checks are supporting signals, not proof.
            </p>
          </div>
        </div>
      </Card>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 360px), 1fr))",
          gap: "1.25rem",
          alignItems: "stretch",
        }}
      >
        <Card style={{ ...panelStyle, padding: "1.25rem" }}>
          <div className="flex items-center justify-between gap-3" style={{ marginBottom: "1rem" }}>
            <div>
              <h3
                className="font-semibold text-gray-900"
                style={{ fontSize: "1.05rem" }}
              >
                Source Image
              </h3>
              <div
                className="flex items-center gap-2 text-gray-500"
                style={{ fontSize: "0.88rem" }}
              >
                <Calendar className="w-4 h-4" />
                {selectedResult.uploadDate.toLocaleString()}
              </div>
            </div>
            <Badge
              variant={
                selectedResult.isAIGenerated ? "destructive" : "default"
              }
            >
              {detectionLabel}
            </Badge>
          </div>

          <div className="flex justify-center">
            <MediaFrame maxWidth="500px">
              <img
                src={selectedResult.imageUrl}
                alt={selectedResult.fileName}
                style={{
                  width: "100%",
                  height: "100%",
                  objectFit: "contain",
                }}
              />
            </MediaFrame>
          </div>
        </Card>

        <Card style={{ ...panelStyle, padding: "1.25rem" }}>
          <h3
            className="font-semibold text-gray-900 mb-2"
            style={{ fontSize: "1.05rem" }}
          >
            Result Summary
          </h3>
          <p className="text-gray-600 mb-5" style={{ fontSize: "0.92rem" }}>
            The detector verdict is the AI-vs-real assessment. The evidence checks below look for metadata and manipulation traces.
          </p>

          <div className="space-y-4">
            <div style={mutedPanelStyle} className="p-4">
              <div
                className="flex justify-between"
                style={{ fontSize: "0.9rem" }}
              >
                <span>Verdict Confidence</span>
                <span>{selectedResult.confidence.toFixed(1)}%</span>
              </div>
              <Progress value={selectedResult.confidence} className="mt-2" />
            </div>

            <div
              className="p-4"
              style={{
                ...mutedPanelStyle,
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
                gap: "0.75rem",
                fontSize: "0.9rem",
              }}
            >
              <div>
                <p className="text-gray-500">File</p>
                <p className="text-gray-900" style={{ wordBreak: "break-word" }}>
                  {selectedResult.fileName}
                </p>
              </div>
              <div>
                  <p className="text-gray-500">Evidence checks</p>
                  <p className="text-gray-900">{evidenceCheckCount}</p>
              </div>
            </div>
          </div>
        </Card>
      </div>

      {(modelEvidence || reliability) && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 320px), 1fr))",
            gap: "1.25rem",
          }}
        >
          {modelEvidence && (
            <Card style={{ ...panelStyle, padding: "1.25rem", gap: "1rem" }}>
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-2">
                  <Server
                    className="w-5 h-5 text-[#655080]"
                    style={{ flexShrink: 0, marginTop: "0.15rem" }}
                  />
                  <div>
                    <h3 className="font-semibold text-gray-900" style={{ fontSize: "1.05rem" }}>
                      Model Evidence
                    </h3>
                    <p className="text-gray-600" style={{ fontSize: "0.9rem", marginTop: "0.2rem" }}>
                      Primary detector output used for the verdict.
                    </p>
                  </div>
                </div>
                <Badge
                  variant="outline"
                  className={`text-xs border shrink-0 ${badgeClassForSignal(modelEvidence.signalStrength)}`}
                >
                  {modelEvidence.signalStrength} signal
                </Badge>
              </div>

              <div style={mutedPanelStyle} className="p-4">
                <div className="flex justify-between" style={{ fontSize: "0.9rem" }}>
                  <span>Raw AI probability</span>
                  <span>{modelEvidence.rawAiProbability.toFixed(1)}%</span>
                </div>
                <Progress value={modelEvidence.rawAiProbability} className="mt-2" />
              </div>

              <div className="space-y-1 pt-1">
                <DetailRow label="Provider" value={labelForProvider(modelEvidence.provider)} />
                <DetailRow label="Provider verdict" value={modelEvidence.providerVerdict ?? "Not supplied"} />
                <DetailRow label="Threshold" value={`${modelEvidence.threshold.toFixed(1)}%`} />
                <DetailRow label="Fallback used" value={modelEvidence.usedFallback ? "Yes" : "No"} />
              </div>

              <p className="text-gray-600" style={{ fontSize: "0.88rem", lineHeight: 1.45 }}>
                {modelEvidence.explanation}
              </p>
            </Card>
          )}

          {reliability && (
            <Card style={{ ...panelStyle, padding: "1.25rem", gap: "1rem" }}>
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-2">
                  <ShieldQuestion
                    className="w-5 h-5 text-[#655080]"
                    style={{ flexShrink: 0, marginTop: "0.15rem" }}
                  />
                  <div>
                    <h3 className="font-semibold text-gray-900" style={{ fontSize: "1.05rem" }}>
                      Result Reliability
                    </h3>
                    <p className="text-gray-600" style={{ fontSize: "0.9rem", marginTop: "0.2rem" }}>
                      How much the report agrees with itself.
                    </p>
                  </div>
                </div>
                <Badge
                  variant="outline"
                  className={`text-xs border shrink-0 ${badgeClassForReliability(reliability.level)}`}
                >
                  {reliability.label}
                </Badge>
              </div>

              <div style={mutedPanelStyle} className="p-4">
                <div className="flex justify-between" style={{ fontSize: "0.9rem" }}>
                  <span>Reliability score</span>
                  <span>{reliability.score.toFixed(1)}%</span>
                </div>
                <Progress value={reliability.score} className="mt-2" />
              </div>

              <p className="text-gray-600" style={{ fontSize: "0.88rem", lineHeight: 1.45 }}>
                {reliability.explanation}
              </p>

              <div className="space-y-1 pt-1">
                {reliability.factors.slice(0, 4).map((factor) => (
                  <div key={factor} className="flex gap-2 text-xs text-gray-600">
                    <span style={{ color: "#655080", fontWeight: 700 }}>-</span>
                    <span>{factor}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      )}

      {robustness && (
        <Card style={{ ...panelStyle, padding: "1.75rem", gap: "1.25rem" }}>
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-start gap-2">
              <Activity
                className="w-5 h-5 text-[#655080]"
                style={{ flexShrink: 0, marginTop: "0.15rem" }}
              />
              <div>
                <h3 className="font-semibold text-gray-900" style={{ fontSize: "1.05rem" }}>
                  Robustness / Stability Check
                </h3>
                <p className="text-gray-600" style={{ fontSize: "0.9rem", marginTop: "0.35rem", lineHeight: 1.5 }}>
                  Re-runs the same detector on safe image variants. This checks consistency, not whether the image is AI by itself.
                </p>
              </div>
            </div>
            <Badge
              variant="outline"
              className={`text-xs border shrink-0 ${badgeClassForRobustness(robustness.status)}`}
            >
              {robustness.label}
            </Badge>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
              gap: "1rem",
            }}
          >
            <div style={{ ...mutedPanelStyle, padding: "1.15rem 1.25rem", minHeight: "126px" }}>
              <p className="text-gray-500" style={{ fontSize: "0.78rem", fontWeight: 700 }}>
                Stability result
              </p>
              <div className="flex items-end justify-between gap-4" style={{ marginTop: "0.55rem" }}>
                <span className="text-gray-900" style={{ fontSize: "1.2rem", fontWeight: 700 }}>
                  {stabilityMeaning(robustness.status)}
                </span>
                <span className="text-gray-500" style={{ fontSize: "0.78rem" }}>
                  consistency index {(robustness.score * 100).toFixed(0)}/100
                </span>
              </div>
              <p className="text-gray-600" style={{ fontSize: "0.82rem", lineHeight: 1.45, marginTop: "0.75rem" }}>
                {robustness.status === "unstable"
                  ? "The detector changed sharply across harmless edits."
                  : robustness.status === "mixed"
                    ? "The detector stayed directionally similar, but scores moved."
                    : "The detector stayed steady across variants."}
              </p>
            </div>
            <div style={{ ...mutedPanelStyle, padding: "1.15rem 1.25rem", minHeight: "126px" }} className="space-y-2">
              <DetailRow label="Variants scored" value={String(robustness.variantCount)} />
              <DetailRow label="Verdict changed" value={hasVariantVerdictFlip(robustness.variants) ? "Yes" : "No"} />
              <DetailRow label="AI score spread" value={robustness.spread == null ? "N/A" : `${robustness.spread.toFixed(1)}%`} />
              <DetailRow
                label="AI score range"
                value={
                  robustness.minAiProbability == null || robustness.maxAiProbability == null
                    ? "N/A"
                    : `${robustness.minAiProbability.toFixed(1)}%-${robustness.maxAiProbability.toFixed(1)}%`
                }
              />
            </div>
          </div>

          <p className="text-gray-600" style={{ fontSize: "0.88rem", lineHeight: 1.45 }}>
            {robustness.explanation}
          </p>

          <div>
            <h4 className="font-medium text-gray-900" style={{ fontSize: "0.92rem", marginBottom: "0.2rem" }}>
              Variant AI Scores
            </h4>
            <p className="text-gray-600" style={{ fontSize: "0.84rem", lineHeight: 1.45, marginBottom: "0.75rem" }}>
              These are raw AI probabilities from each variant. The bad sign is a wide spread or a verdict flip, not one tile by itself.
            </p>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
              gap: "0.85rem",
            }}
          >
            {robustness.variants.slice(0, 8).map((variant) => (
              <div
                key={variant.name}
                style={{
                  ...mutedPanelStyle,
                  padding: "1rem",
                  minHeight: "94px",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between",
                }}
              >
                <div className="flex items-start justify-between gap-2">
                  <p className="text-gray-500 text-xs" style={{ textTransform: "capitalize", lineHeight: 1.35 }}>
                    {variant.name}
                  </p>
                  <Badge
                    variant="outline"
                    className={`text-xs border shrink-0 ${variantBadgeClass(variant.verdict)}`}
                  >
                    {variantVerdictLabel(variant.verdict)}
                  </Badge>
                </div>
                <div>
                  <p className="text-gray-900 text-sm" style={{ fontWeight: 700, marginTop: "0.55rem" }}>
                    {variant.aiProbability.toFixed(1)}%
                  </p>
                  <p className="text-gray-500" style={{ fontSize: "0.74rem", marginTop: "0.15rem" }}>
                    raw AI probability
                  </p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {aiSpecificTests.length > 0 && (
        <Card
          style={{
            ...panelStyle,
            padding: "1.5rem",
            gap: "1.25rem",
          }}
        >
          <div
            className="flex items-start justify-between gap-3"
            style={{ alignItems: "flex-start" }}
          >
            <div className="flex items-start gap-2">
              <ShieldCheck
                className="w-5 h-5 text-[#655080]"
                style={{ flexShrink: 0, marginTop: "0.15rem" }}
              />
              <div>
                <h3
                  className="font-semibold text-gray-900"
                  style={{ fontSize: "1.05rem", lineHeight: 1.25 }}
                >
                  AI-Specific Evidence Checks
                </h3>
                <p
                  className="text-gray-600"
                  style={{ fontSize: "0.92rem", lineHeight: 1.45, marginTop: "0.25rem" }}
                >
                  Checks for AI provenance plus frequency, reconstruction, visual, and structure signals. These review signals are not standalone proof.
                </p>
              </div>
            </div>
            <Badge variant="secondary" style={{ flexShrink: 0 }}>
              {aiSpecificTests.length} AI {aiSpecificTests.length === 1 ? "check" : "checks"}
            </Badge>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 300px), 340px))",
              gap: "1rem",
              justifyContent: "start",
            }}
          >
            {aiSpecificTests.map((test, index) => (
              <ForensicTestCard
                key={`${selectedResult.id}-${test.test_name}-${index}`}
                test={test}
              />
            ))}
          </div>
        </Card>
      )}

      <Card
        style={{
          ...panelStyle,
          padding: "1.5rem",
          gap: "1.25rem",
        }}
      >
        <div
          className="flex items-start justify-between gap-3"
          style={{ alignItems: "flex-start" }}
        >
          <div>
            <h3
              className="font-semibold text-gray-900"
              style={{ fontSize: "1.05rem", lineHeight: 1.25 }}
            >
              Manipulation Evidence Checks
            </h3>
            <p
              className="text-gray-600"
              style={{ fontSize: "0.92rem", lineHeight: 1.45, marginTop: "0.25rem" }}
            >
              Checks for edits, clones, compression mismatches, and local texture shifts. Clean results do not rule out AI generation.
            </p>
          </div>
          <Badge variant="secondary" style={{ flexShrink: 0 }}>
            {manipulationTests.length} evidence {manipulationTests.length === 1 ? "check" : "checks"}
          </Badge>
        </div>

        {manipulationTests.length === 0 ? (
          <p className="text-gray-600" style={{ fontSize: "0.92rem" }}>
            No forensic evidence maps were available for this file.
          </p>
        ) : (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 300px), 340px))",
              gap: "1rem",
              justifyContent: "start",
            }}
          >
            {manipulationTests.map((test, index) => (
              <ForensicTestCard
                key={`${selectedResult.id}-${test.test_name}-${index}`}
                test={test}
              />
            ))}
          </div>
        )}
      </Card>

      <Card className="bg-purple-100" style={{ ...panelStyle, padding: "1.25rem", gap: "1rem" }}>
        <h3 className="text-gray-900" style={{ fontSize: "1.05rem" }}>Plain-Language Summary</h3>
        {userSummary ? (
          <>
            <div
              style={{
                ...mutedPanelStyle,
                padding: "1rem",
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
                gap: "0.75rem",
              }}
            >
              <div>
                <p className="text-gray-500" style={{ fontSize: "0.78rem", fontWeight: 700 }}>
                  Final Verdict
                </p>
                <p className="text-gray-900" style={{ fontSize: "1rem", fontWeight: 700 }}>
                  {userSummary["Final Verdict"]}
                </p>
              </div>
              <div>
                <p className="text-gray-500" style={{ fontSize: "0.78rem", fontWeight: 700 }}>
                  Confidence
                </p>
                <p className="text-gray-900" style={{ fontSize: "1rem", fontWeight: 700 }}>
                  {userSummary.Confidence}
                </p>
              </div>
            </div>

            <div className="space-y-3">
              <div>
                <p className="text-gray-500" style={{ fontSize: "0.78rem", fontWeight: 700 }}>
                  Summary
                </p>
                <p className="text-gray-700" style={{ fontSize: "0.92rem" }}>
                  {userSummary.Summary}
                </p>
              </div>
              <div>
                <p className="text-gray-500" style={{ fontSize: "0.78rem", fontWeight: 700 }}>
                  Forensic Insight
                </p>
                <p className="text-gray-700" style={{ fontSize: "0.92rem" }}>
                  {userSummary["Forensic Insight"]}
                </p>
              </div>
              <div>
                <p className="text-gray-500" style={{ fontSize: "0.78rem", fontWeight: 700 }}>
                  Recommendation
                </p>
                <p className="text-gray-700" style={{ fontSize: "0.92rem" }}>
                  {userSummary.Recommendation}
                </p>
              </div>
            </div>
          </>
        ) : (
          <p className="text-gray-700" style={{ fontSize: "0.92rem" }}>
            The overall confidence score of{" "}
            {selectedResult.confidence.toFixed(1)}% suggests that it is{" "}
            {selectedResult.isAIGenerated
              ? "likely AI-generated"
              : "not strongly flagged as AI-generated"}. Clean forensic checks do not prove camera origin.
          </p>
        )}
      </Card>
    </div>
  );
}
