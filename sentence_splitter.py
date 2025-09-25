# sentence_splitter.py

import re

# This is a Python translation of the JavaScript logic you provided.
# It handles common abbreviations to avoid splitting sentences incorrectly.

EXCEPTION_STRING = '...; Mr.; Mrs.; Dr.; Jr.; Sr.; Prof.; St.; Ave.; Corp.; Inc.; Ltd.; Co.; Gov.; Capt.; Sgt.; et al.; vs.; e.t.a.; .A.; .B.; .C.; .D.; .E.; .F.; .G.; .H.; .I.; .J.; .K.; .L.; .M.; .N.; .O.; .P.; .Q.; .R.; .S.; .T.; .U.; .V.; .W.; .X.; .Y.; .Z.;  A.;  B.;  C.;  D.;  E.;  F.;  G.;  H.;  I.;  J.;  K.;  L.;  M.;  N.;  O.;  P.;  Q.;  R.;  S.;  T.;  U.;  V.;  W.;  X.;  Y.;  Z.; .a.; .b.; .c.; .d.; .e.; .f.; .g.; .h.; .i.; .j.; .k.; .l.; .m.; .n.; .o.; .p.; .q.; .r.; .s.; .t.; .u.; .v.; .w.; .x.; .y.; .z.; .a; .b; .c; .d; .e; .f; .g; .h; .i; .j; .k; .l; .m; .n; .o; .p; .q; .r; .s; .t; .u; .v; .w; .x; .y; .z; 0.0; 0.1; 0.2; 0.3; 0.4; 0.5; 0.6; 0.7; 0.8; 0.9; 1.0; 1.1; 1.2; 1.3; 1.4; 1.5; 1.6; 1.7; 1.8; 1.9; 2.0; 2.1; 2.2; 2.3; 2.4; 2.5; 2.6; 2.7; 2.8; 2.9; 3.0; 3.1; 3.2; 3.3; 3.4; 3.5; 3.6; 3.7; 3.8; 3.9; 4.0; 4.1; 4.2; 4.3; 4.4; 4.5; 4.6; 4.7; 4.8; 4.9; 5.0; 5.1; 5.2; 5.3; 5.4; 5.5; 5.6; 5.7; 5.8; 5.9; 6.0; 6.1; 6.2; 6.3; 6.4; 6.5; 6.6; 6.7; 6.8; 6.9; 7.0; 7.1; 7.2; 7.3; 7.4; 7.5; 7.6; 7.7; 7.8; 7.9; 8.0; 8.1; 8.2; 8.3; 8.4; 8.5; 8.6; 8.7; 8.8; 8.9; 9.0; 9.1; 9.2; 9.3; 9.4; 9.5; 9.6; 9.7; 9.8; 9.9; .0; .1; .2; .3; .4; .5; .6; .7; .8; .9;'
PERIOD_EXCEPTIONS = EXCEPTION_STRING.split('; ')

def split_into_sentences(text):
    """
    Splits text into sentences using a placeholder method for exceptions.
    """
    # Use a unique, unlikely placeholder
    placeholder = "[[PERIOD_PLACEHOLDER]]"
    
    # Replace periods in known exceptions with the placeholder
    for exc in PERIOD_EXCEPTIONS:
        text = text.replace(exc, exc.replace(".", placeholder))

    # Split text by sentence-ending punctuation. The regex keeps the delimiters.
    sentences_raw = re.split(r'([.!?])', text)
    
    sentences = []
    # Combine the text parts with their corresponding punctuation
    for i in range(0, len(sentences_raw) - 1, 2):
        sentence = (sentences_raw[i] + sentences_raw[i+1]).strip()
        if sentence:
            # Restore the original periods from the placeholders
            sentences.append(sentence.replace(placeholder, "."))

    # Add the last part if it exists (for text not ending in punctuation)
    if len(sentences_raw) % 2 == 1 and sentences_raw[-1].strip():
        last_part = sentences_raw[-1].strip()
        sentences.append(last_part.replace(placeholder, "."))
        
    return sentences
