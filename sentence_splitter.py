# sentence_splitter.py
import re

# This is a Python translation of the JavaScript logic you provided.
# It handles common abbreviations to avoid splitting sentences incorrectly.
EXCEPTION_STRING = '...; Mr.; Mrs.; Dr.; Jr.; Sr.; Prof.; St.; Ave.; Corp.; Inc.; Ltd.; Co.; Gov.; Capt.; Sgt.; et al.; vs.; e.t.a.; .A.; .B.; .C.; .D.; .E.; .F.; .G.; .H.; .I.; .J.; .K.; .L.; .M.; .N.; .O.; .P.; .Q.; .R.; .S.; .T.; .U.; .V.; .W.; .X.; .Y.; .Z.;  A.;  B.;  C.;  D.;  E.;  F.;  G.;  H.;  I.;  J.;  K.;  L.;  M.;  N.;  O.;  P.;  Q.;  R.;  S.;  T.;  U.;  V.;  W.;  X.;  Y.;  Z.; .a.; .b.; .c.; .d.; .e.; .f.; .g.; .h.; .i.; .j.; .k.; .l.; .m.; .n.; .o.; .p.; .q.; .r.; .s.; .t.; .u.; .v.; .w.; .x.; .y.; .z.; .a; .b; .c; .d; .e; .f; .g; .h; .i; .j; .k; .l; .m; .n; .o; .p; .q; .r; .s; .t; .u; .v; .w; .x; .y; .z; 0.0; 0.1; 0.2; 0.3; 0.4; 0.5; 0.6; 0.7; 0.8; 0.9; 1.0; 1.1; 1.2; 1.3; 1.4; 1.5; 1.6; 1.7; 1.8; 1.9; 2.0; 2.1; 2.2; 2.3; 2.4; 2.5; 2.6; 2.7; 2.8; 2.9; 3.0; 3.1; 3.2; 3.3; 3.4; 3.5; 3.6; 3.7; 3.8; 3.9; 4.0; 4.1; 4.2; 4.3; 4.4; 4.5; 4.6; 4.7; 4.8; 4.9; 5.0; 5.1; 5.2; 5.3; 5.4; 5.5; 5.6; 5.7; 5.8; 5.9; 6.0; 6.1; 6.2; 6.3; 6.4; 6.5; 6.6; 6.7; 6.8; 6.9; 7.0; 7.1; 7.2; 7.3; 7.4; 7.5; 7.6; 7.7; 7.8; 7.9; 8.0; 8.1; 8.2; 8.3; 8.4; 8.5; 8.6; 8.7; 8.8; 8.9; 9.0; 9.1; 9.2; 9.3; 9.4; 9.5; 9.6; 9.7; 9.8; 9.9; .0; .1; .2; .3; .4; .5; .6; .7; .8; .9;'
PERIOD_EXCEPTIONS = [exc.strip() for exc in EXCEPTION_STRING.split('; ') if exc.strip()]

def split_into_sentences(text):
    """
    Splits text into sentences using a placeholder method for exceptions.
    Handles edge cases better and provides debug information.
    """
    if not text or not text.strip():
        return []
    
    # Clean up the text
    text = text.strip()
    
    # Use a unique, unlikely placeholder
    placeholder = "[[PERIOD_PLACEHOLDER]]"
    
    # Replace periods in known exceptions with the placeholder
    original_text = text
    for exc in PERIOD_EXCEPTIONS:
        if exc in text:
            text = text.replace(exc, exc.replace(".", placeholder))
    
    # Split text by sentence-ending punctuation, keeping the delimiters
    # This regex captures the punctuation marks
    sentences_raw = re.split(r'([.!?]+)', text)
    
    sentences = []
    i = 0
    while i < len(sentences_raw):
        if i + 1 < len(sentences_raw):
            # Combine text with its punctuation
            sentence_text = sentences_raw[i].strip()
            punctuation = sentences_raw[i + 1].strip()
            
            if sentence_text:  # Only add non-empty sentences
                full_sentence = sentence_text + punctuation
                # Restore the original periods from the placeholders
                full_sentence = full_sentence.replace(placeholder, ".")
                sentences.append(full_sentence.strip())
            
            i += 2
        else:
            # Handle the last part if it doesn't end with punctuation
            last_part = sentences_raw[i].strip()
            if last_part:
                last_part = last_part.replace(placeholder, ".")
                sentences.append(last_part)
            i += 1
    
    # Filter out very short or empty sentences
    sentences = [s for s in sentences if len(s.strip()) > 3]
    
    return sentences
