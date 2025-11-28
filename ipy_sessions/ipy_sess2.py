# coding: utf-8
get_ipython().run_line_magic('run', 'ipy_sess.py')
df
columns
yplayers[0].keys()
yplayers[0]['stats_id']
matchups = api.matchups(13)
matchups
jmespath.search(f"[?owner_id=='{yoshid}'].player_pounts", matchups)
yoshid
jmespath.search(f"[?owner_id=='{yoshid}'].player_points", matchups)
matchups[0].keys()
jmespath.search(f"[?owner_id=='{yoshid}'].players_points", matchups)
jmespath.search(f"[?owner_id=='{yoshid}']", matchups)
matchups[0]['roster_id']
matchups
m0 = matchups[0]
for k, v in m0.items():
    print(f"{k:10}{str(v)[:30]}")
matchups = api.matchups()
matchups = api.matchups(13)
for k, v in m0.items():
    print(f"{k:10}{str(v)[:30]}")
for k, v in m0.items():
    print(f"{k:20}{str(v)[:30]}")
