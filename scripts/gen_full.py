import base64

content = base64.b64decode('').decode('utf-8')

with open('PHASE_8_2_2_FMP_LIVE_VALIDATION_REPORT.md','w',encoding='utf-8') as f:
    f.write(content)

print('done')
