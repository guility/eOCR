"""Small fictional documents used to bring up corpus tooling."""

from pathlib import Path

OUT = Path.cwd() / ".delta" / "corpus" / "seed"
FIXTURES = {
    "en": {"font": "Noto Sans", "title": "Technical process fixture",
           "body": "The system preserves the order of text, tables, diagrams, and source graphics.",
           "caption": "Reference equation:", "table": ["PDF input", "OCR stage", "Editable DOCX"],
           "formula": "x + y = z", "language": "en"},
    "ru": {"font": "Noto Sans", "title": "Технический документ для проверки",
           "body": "Система сохраняет порядок текста, таблиц, схем и исходной графики.",
           "caption": "Эталонная формула:", "table": ["Вход PDF", "Распознавание", "Редактируемый DOCX"],
           "formula": "x + y = z", "language": "ru"},
    "zh-cn": {"font": "Noto Sans CJK SC", "title": "技术文档测试样例",
              "body": "系统保留文本、表格、示意图和原始图形的顺序。", "caption": "参考公式：",
              "table": ["PDF 输入", "识别阶段", "可编辑 DOCX"], "formula": "x + y = z", "language": "zh-Hans"},
    "zh-tw": {"font": "Noto Sans CJK TC", "title": "技術文件測試樣例",
              "body": "系統保留文字、表格、示意圖和原始圖形的順序。", "caption": "參考公式：",
              "table": ["PDF 輸入", "辨識階段", "可編輯 DOCX"], "formula": "x + y = z", "language": "zh-Hant"},
}
