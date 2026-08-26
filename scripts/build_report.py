lines=[]
lines.append('test')
open('out.txt','w').write(chr(10).join(lines))
print('ok')
