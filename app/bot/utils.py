def split_md(text:str, maxlen:int=3500):
    parts=[]
    cur=""
    for line in text.splitlines(True):
        if len(cur)+len(line) > maxlen:
            parts.append(cur)
            cur=line
        else:
            cur+=line
    if cur: parts.append(cur)
    return parts
