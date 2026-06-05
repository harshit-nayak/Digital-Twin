import urllib.request, json

# Test memory endpoint
r = urllib.request.urlopen('http://localhost:8000/memory/test_user/einstein', timeout=5)
data = json.loads(r.read().decode())
print('MEMORY endpoint: OK')
print('  user_id:', data['user_id'])
print('  total memories:', data['total'])

# Test admin health
r = urllib.request.urlopen('http://localhost:8000/admin/health', timeout=5)
data = json.loads(r.read().decode())
print('ADMIN health:', data)

# Test timeline
r = urllib.request.urlopen('http://localhost:8000/scientists/einstein/timeline', timeout=5)
data = json.loads(r.read().decode())
print('TIMELINE:', len(data['milestones']), 'milestones')
for m in data['milestones'][:3]:
    print(f"  {m['year']}: {m['label']}")
