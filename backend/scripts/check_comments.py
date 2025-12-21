import zipfile
p = 'backend/uploads/format_check/annotate/20251221_234404_20251221_215147_docx_annotated.docx'
print("Checking:", p)
try:
    with zipfile.ZipFile(p) as z:
        entries = [e.filename for e in z.infolist() if e.filename.startswith('word/')]
        print("ENTRIES::", entries)
        try:
            s = z.read('word/comments.xml').decode('utf-8')
            print("COMMENTS_XML::")
            print(s[:2000])
        except KeyError:
            print("NO_COMMENTS_XML")
except Exception as e:
    print("ERR", e)





