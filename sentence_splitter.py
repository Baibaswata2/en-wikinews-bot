# sentence_splitter.py
import re

EXCEPTION_STRING = '...; Mr.; Mrs.; Dr.; Jr.; Sr.; Prof.; St.; Ave.; Corp.; Inc.; Ltd.; Co.; Gov.; Capt.; Sgt.; et al.; vs.; e.t.a.; .A.; .B.; .C.; .D.; .E.; .F.; .G.; .H.; .I.; .J.; .K.; .L.; .M.; .N.; .O.; .P.; .Q.; .R.; .S.; .T.; .U.; .V.; .W.; .X.; .Y.; .Z.;  A.;  B.;  C.;  D.;  E.;  F.;  G.;  H.;  I.;  J.;  K.;  L.;  M.;  N.;  O.;  P.;  Q.;  R.;  S.;  T.;  U.;  V.;  W.;  X.;  Y.;  Z.; .a.; .b.; .c.; .d.; .e.; .f.; .g.; .h.; .i.; .j.; .k.; .l.; .m; .n.; .o.; .p.; .q.; .r.; .s.; .t.; .u.; .v.; .w.; .x.; .y.; .z.; .a; .b; .c; .d; .e; .f; .g; .h; .i; .j; .k; .l; .m; .n; .o; .p; .q; .r; .s; .t; .u; .v; .w; .x; .y; .z; 0.0; 0.1; 0.2; 0.3; 0.4; 0.5; 0.6; 0.7; 0.8; 0.9; 1.0; 1.1; 1.2; 1.3; 1.4; 1.5; 1.6; 1.7; 1.8; 1.9; 2.0; 2.1; 2.2; 2.3; 2.4; 2.5; 2.6; 2.7; 2.8; 2.9; 3.0; 3.1; 3.2; 3.3; 3.4; 3.5; 3.6; 3.7; 3.8; 3.9; 4.0; 4.1; 4.2; 4.3; 4.4; 4.5; 4.6; 4.7; 4.8; 4.9; 5.0; 5.1; 5.2; 5.3; 5.4; 5.5; 5.6; 5.7; 5.8; 5.9; 6.0; 6.1; 6.2; 6.3; 6.4; 6.5; 6.6; 6.7; 6.8; 6.9; 7.0; 7.1; 7.2; 7.3; 7.4; 7.5; 7.6; 7.7; 7.8; 7.9; 8.0; 8.1; 8.2; 8.3; 8.4; 8.5; 8.6; 8.7; 8.8; 8.9; 9.0; 9.1; 9.2; 9.3; 9.4; 9.5; 9.6; 9.7; 9.8; 9.9. .0; .1; .2; .3; .4; .5; .6; .7; .8; .9;'

PERIOD_PLACEHOLDER = 'PERIOD_PLACEHOLDER'
EXCEPTION_STRING_SEPARATOR = '; '
PERIOD_EXCEPTIONS = EXCEPTION_STRING.split(EXCEPTION_STRING_SEPARATOR)
PERIOD_EXCEPTION_PLACEHOLDERS = EXCEPTION_STRING.replace('.', PERIOD_PLACEHOLDER).split(EXCEPTION_STRING_SEPARATOR)

def insert_placeholders(text, period_exceptions, period_exception_placeholders):
    modified_text = text
    for i in range(len(period_exceptions)):
        modified_text = modified_text.replace(period_exceptions[i], period_exception_placeholders[i])
    return modified_text

def remove_placeholders(text, period_exceptions, period_exception_placeholders):
    modified_text = text
    for i in range(len(period_exceptions)):
        modified_text = modified_text.replace(period_exception_placeholders[i], period_exceptions[i])
    return modified_text

def split_into_sentences(text):
    if not text:
        return []
    
    # First, apply the placeholders for exceptions
    modified_text = insert_placeholders(text, PERIOD_EXCEPTIONS, PERIOD_EXCEPTION_PLACEHOLDERS)
    
    # Split the text at sentence boundaries (., !, ?)
    sentence_parts = re.split(r'([.!?])', modified_text)
    sentences = []
    
    i = 0
    while i < len(sentence_parts) - 1:
        if i + 1 < len(sentence_parts):
            # Join the text part with its punctuation
            sentence = sentence_parts[i] + sentence_parts[i + 1]
            
            # Check if next part starts with a closing quotation mark
            if i + 2 < len(sentence_parts) and sentence_parts[i + 2].strip().startswith('"'):
                # Extract just the quotation mark and add it to this sentence
                next_part = sentence_parts[i + 2].strip()
                quote_match = re.match(r'^"+', next_part)
                if quote_match:
                    sentence += quote_match.group(0)
                    # Remove the quotation mark from the next part so it's not duplicated
                    sentence_parts[i + 2] = next_part[len(quote_match.group(0)):]
            
            # Restore original periods/exceptions
            sentence = remove_placeholders(sentence, PERIOD_EXCEPTIONS, PERIOD_EXCEPTION_PLACEHOLDERS)
            sentences.append(sentence)
        
        i += 2
    
    # Handle the last part if it exists (for text not ending in punctuation)
    if len(sentence_parts) % 2 == 1:
        last_part = sentence_parts[-1].strip()
        if len(last_part) > 0:
            last_part = remove_placeholders(last_part, PERIOD_EXCEPTIONS, PERIOD_EXCEPTION_PLACEHOLDERS)
            sentences.append(last_part)
    
    return sentences

def remove_comments(text):
    """Remove HTML comments"""
    return re.sub(r'<!--[\s\S]*?-->', '', text)

def remove_notice_templates(text):
    """Remove notice templates"""
    return re.sub(
        r'\{\{(?:Ombox|[Aa]mbox|[Mm]box|[Nn]otice|[Mm]essage)[^}]*?\|\s*text\s*=\s*([^}\|]+)(?:[^}]*?)\}\}',
        r'\1',
        text
    )

def fix_wikilinks(text):
    """Fix W| template wikilinks"""
    def replace_w_template(match):
        p1 = match.group(1)
        p2 = match.group(2) if match.group(2) else None
        return f"[[{p2}]]" if p2 else f"[[{p1}]]"
    
    return re.sub(
        r'\{\{[Ww]\|((?:[^|{}]|\{\{[^{}]*\}\})*?)(?:\|((?:[^|{}]|\{\{[^{}]*\}\})*?))?\}\}',
        replace_w_template,
        text
    )

def remove_media_links(text):
    """Remove media links with proper bracket matching"""
    # Simple media links first
    cleaned_text = re.sub(r'\[\[(?:File|Image|Media):[^\[\]]*?\]\]', '', text, flags=re.IGNORECASE)
    
    # Handle nested brackets
    while re.search(r'\[\[(?:File|Image|Media):', cleaned_text, re.IGNORECASE):
        start_match = re.search(r'\[\[(?:File|Image|Media):', cleaned_text, re.IGNORECASE)
        if not start_match:
            break
        
        start_index = start_match.start()
        depth = 1
        end_index = start_index + 2
        
        while depth > 0 and end_index < len(cleaned_text) - 1:
            if cleaned_text[end_index:end_index + 2] == '[[':
                depth += 1
                end_index += 2
            elif cleaned_text[end_index:end_index + 2] == ']]':
                depth -= 1
                end_index += 2
            else:
                end_index += 1
        
        if depth == 0:
            cleaned_text = cleaned_text[:start_index] + cleaned_text[end_index:]
        else:
            break  # Avoid infinite loop if brackets don't match
    
    return cleaned_text

def remove_templates(text):
    """Remove templates with proper bracket matching"""
    # Simple template removal pattern
    strip_templates = re.compile(r'\{\{[^\}\{]*(?:\{\{[^\}\{]*(?:\{\{[^\}\{]*(?:\{\{[^\}\{]*\}\})?\}\})?\}\})?\}\}')
    while re.search(r'\{\{[^\}]*\}\}', text):
        text = strip_templates.sub('', text)
    return text

def remove_categories(text):
    """Remove category links"""
    return re.sub(r'\[\[(?:Category):[\s\S]*?\]\]', '', text, flags=re.IGNORECASE)

def clean_formatting(text):
    """Remove wiki formatting"""
    text = re.sub(r"'''''(.+?)'''''", r'\1', text)  # Bold italic
    text = re.sub(r"'''(.+?)'''", r'\1', text)      # Bold
    text = re.sub(r"''(.+?)''", r'\1', text)        # Italic
    text = re.sub(r'[«»‹›『』「」]', '', text)        # Quote marks
    return text

def handle_links(text):
    """Handle wiki links and external links"""
    # Handle piped links [[link|display]] -> display
    piped_link = re.compile(r'\[\[(?:[^|\]]*\|)?([^\]]+)\]\]')
    while re.search(r'\[\[', text):
        text = piped_link.sub(r'\1', text)
    
    # Handle external links [url display] -> display
    text = re.sub(r'\[(?:https?|ftp|gopher|irc)://[^\]\s]*(?:\s+([^\]]+))?\]', r'\1 ', text)
    return text

def remove_html_and_tables(text):
    """Remove HTML tags, references, and tables"""
    text = re.sub(r'<ref[^>]*?>[\s\S]*?</ref>', '', text)  # References with content
    text = re.sub(r'<ref[^>\/]*?/>', '', text)             # Self-closing references
    text = re.sub(r'<[^>]+>', '', text)                    # All HTML tags
    text = re.sub(r'\{\|[\s\S]*?\|\}', '', text)          # Tables
    return text

def clean_whitespace(text):
    """Clean up whitespace and entities"""
    text = re.sub(r'(\r\n|\n|\r)', ' ', text)     # Line breaks to spaces
    text = re.sub(r'&nbsp;', ' ', text)           # Non-breaking spaces
    text = re.sub(r'&[a-z]+;', '', text)          # HTML entities
    text = re.sub(r'\s+', ' ', text)              # Multiple spaces to single
    return text.strip()

def remove_headers(text):
    """Remove section headers"""
    return re.sub(r'==+\s*[^=]+\s*==+', '', text)

def cleanup_content(content, sentence_count=2):
    if not content:
        return ''
    
    clean_text = content
    
    # Apply all cleaning steps in order
    clean_text = remove_comments(clean_text)
    clean_text = remove_notice_templates(clean_text)
    clean_text = fix_wikilinks(clean_text)
    clean_text = remove_media_links(clean_text)
    clean_text = remove_templates(clean_text)
    clean_text = remove_categories(clean_text)
    clean_text = clean_formatting(clean_text)
    clean_text = handle_links(clean_text)
    clean_text = remove_html_and_tables(clean_text)
    clean_text = clean_whitespace(clean_text)
    clean_text = remove_headers(clean_text)
    
    # Split into sentences and filter
    sentences = split_into_sentences(clean_text)
    sentences = [s.strip() for s in sentences if 0 < len(s) < 500]
    sentences = sentences[:sentence_count]
    
    return ' '.join(sentences).strip()
