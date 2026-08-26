lines=[]
for i in range(10):
    lines.append(f'Line {i}')

open('PHASE_8_2_2_FMP_LIVE_VALIDATION_REPORT.md','w',encoding='utf-8').write(chr(10).join(lines))
print('done')
