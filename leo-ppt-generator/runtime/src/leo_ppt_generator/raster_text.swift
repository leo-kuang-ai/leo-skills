import Foundation
import Vision

// 只读取实际图片，不接收预期文字或模板声明作为识别提示。
let request = VNRecognizeTextRequest()
request.revision = VNRecognizeTextRequestRevision3
request.recognitionLevel = .accurate
request.usesLanguageCorrection = false
request.recognitionLanguages = ["zh-Hans", "en-US"]
try VNImageRequestHandler(url: URL(fileURLWithPath: CommandLine.arguments[1])).perform([request])
let texts: [[String: Any]] = (request.results ?? []).compactMap { observation in
    guard let candidate = observation.topCandidates(1).first else { return nil }
    let box = observation.boundingBox
    return ["text": candidate.string, "confidence": candidate.confidence,
            "box": [box.minX, 1 - box.maxY, box.width, box.height]]
}
let data = try JSONSerialization.data(withJSONObject: texts, options: [.sortedKeys])
print(String(data: data, encoding: .utf8)!)
