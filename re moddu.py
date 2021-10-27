import re
mystr = "this is a string aand 32777 4545454545 this do nothin454545 g and i am checking or not don't worry about anything even about my 45454545454english 454554545445dthank you aiai54545aiaaiaiaiiaiaiaiiaiiaii"
# patt = re.compile(r'this')
# patt = re.compile(r'.do')
# patt = re.compile(r'^do')
# patt = re.compile(r'you$')
# patt = re.compile(r'ai{2}')
# patt = re.compile(r'(ai){1}')
# patt = re.compile(r'aii{1}|this')
# patt = re.compile(r'aii{1}|this')
# patt = re.compile(r'string\b')
# patt = re.compile(r'is\b')
patt = re.compile(r'\d{4}\d{5}')
matches = patt.finditer(mystr)
for match in matches:
        print(match)