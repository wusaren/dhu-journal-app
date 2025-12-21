import sys, os, json
sys.path.insert(0, os.path.abspath(os.path.join(os.getcwd(), 'backend')))
from services.chinese_annotation_engine import abstract_adapter, keywords_adapter
from services.Chinese_paper_detect import Abstract_detect, Keywords_detect_unified

DOC = r'backend\\uploads\\format_check\\temp\\20251221_215147_docx'

def run():
    # run detectors directly to avoid importing the full detector which may require extra deps
    tpl_dir = os.path.join('backend', 'services', 'Chinese_paper_detect_templates')
    abstract_tpl = os.path.join(tpl_dir, 'Abstract.json')
    english_tpl = os.path.join(tpl_dir, 'English_Abstract.json')
    abstract_report = Abstract_detect.check_abstract_with_template(DOC, abstract_tpl)
    try:
        english_report = Abstract_detect.check_english_abstract_with_template(DOC, english_tpl)
    except Exception:
        english_report = {'error': True, 'summary': ['english abstract check failed']}
    keywords_report = Keywords_detect_unified.check_bilingual_keywords(DOC, None, None)

    all_reports = {
        'Abstract': abstract_report,
        'English_Abstract': english_report,
        'Keywords': keywords_report
    }
    print("Collected report keys:", list(all_reports.keys()))

    a_issues = abstract_adapter(all_reports)
    print(f"Abstract adapter produced {len(a_issues)} issues")
    for it in a_issues:
        print("ISSUE:", it.module, it.section, "locate:", it.locate_method, it.locate_data)

    k_issues = keywords_adapter(all_reports)
    print(f"Keywords adapter produced {len(k_issues)} issues")
    for it in k_issues:
        print("ISSUE:", it.module, it.section, "locate:", it.locate_method, it.locate_data)

if __name__ == '__main__':
    run()


