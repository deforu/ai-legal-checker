import xml.etree.ElementTree as ET
import json
import os
import sys

def parse_law_xml(file_path):
    print(f"Parsing {file_path}...")
    
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        articles_data = []
        
        # 本則 (MainProvision) の抽出
        main_provision = root.find(".//MainProvision")
        if main_provision is not None:
            articles_data.extend(extract_articles_from_element(main_provision, is_main=True))
            
        # 附則 (SupplProvision) は抽出しない（ノイズ削減のため）
        # suppl_provisions = root.findall(".//SupplProvision")
        # for suppl in suppl_provisions:
        #     articles_data.extend(extract_articles_from_element(suppl, is_main=False))
            
        return articles_data

    except Exception as e:
        print(f"Error parsing XML: {e}")
        return []

def extract_articles_from_element(element, is_main):
    """特定の要素配下のArticleを抽出する共通関数"""
    articles = []
    for article in element.findall(".//Article"):
        title = article.find("ArticleTitle")
        caption = article.find("ArticleCaption")
        
        title_text = title.text if title is not None else "不明な条文"
        caption_text = caption.text if caption is not None else ""
        
        content_text = ""
        for paragraph in article.findall("Paragraph"):
            para_num = paragraph.find("ParagraphNum")
            para_num_text = para_num.text if para_num is not None else ""
            
            para_sentence = paragraph.find("ParagraphSentence")
            if para_sentence is not None:
                for sentence in para_sentence.findall("Sentence"):
                    if sentence.text:
                        content_text += f"{para_num_text} {sentence.text}\n"
            
            for item in paragraph.findall("Item"):
                item_title = item.find("ItemTitle")
                item_title_text = item_title.text if item_title is not None else ""
                item_sentence = item.find("ItemSentence")
                if item_sentence is not None:
                    for sentence in item_sentence.findall(".//Sentence"):
                        if sentence.text:
                            content_text += f"  {item_title_text} {sentence.text}\n"

        articles.append({
            "title": f"不当景品類及び不当表示防止法 {title_text} {caption_text}",
            "law_category": "premiums_and_representations_act",
            "section": title_text,
            "tags": ["景品表示法", caption_text] if caption_text else ["景品表示法"],
            "content": content_text.strip(),
            "metadata": {
                "is_main_provision": is_main # ここで本則か附則かを区別
            }
        })
    return articles

def main():
    xml_path = "不当景品類及び不当表示防止法（昭和三十七年法律第百三十四号）.xml"
    
    if not os.path.exists(xml_path):
        print(f"File not found: {xml_path}")
        return

    articles = parse_law_xml(xml_path)
    print(f"\n抽出された条文数: {len(articles)}")
    
    if articles:
        print("\n--- 抽出サンプル (最初の3件) ---")
        for i, article in enumerate(articles[:3]):
            print(f"\n[{i+1}] {article['title']}")
            print(f"内容: {article['content'][:100]}...")
            
        # JSONファイルとして保存（RAGロード用）
        output_path = "data/legal_documents/full_premiums_act.json"
        
        # 既存のJSONファイルを上書きしないようにリスト形式で保存する形に変換するか、
        # あるいは1つのファイルにまとめるか。
        # ここでは、load_sample_documentsが個別のファイルを想定しているため、
        # 1つの大きなJSONファイルとして保存します。
        # ただし、app/rag/retrieval.py の load_sample_documents は
        # 各ファイルが {title:..., content:...} という辞書であることを期待しているかもしれません。
        # 先ほどの stealth_marketing.json を見ると単一オブジェクトです。
        # 複数の条文を一括ロードするには、retrieval.py の改修か、
        # あるいは「条文ごとに別ファイル」にするか、「リスト形式のJSON」に対応させる必要があります。
        
        # 今回は効率のため、「リスト形式のJSON」を作成し、
        # データロードスクリプト(init_data.py)側でそれをループして登録するように対応させます。
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(articles, f, ensure_ascii=False, indent=4)
        print(f"\nデータを {output_path} に保存しました。")

if __name__ == "__main__":
    main()
