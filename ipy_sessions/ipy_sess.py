# coding: utf-8
import pandas as pd
import sys
sys.path.append("bin")
from sleeper import *
api = SleeperAPI(1265656840373403648)
import jmespath
users = api.users()
# jmespath.search("[*].[metadata.team_name,user_id]", users)
yoshid = [id for id in [user['user_id'] for user in users if 'metadata' in user and 'team_name' in user['metadata'] and user['metadata']['team_name'].startswith('Yoshi')]][0]
print(f"Yoshimi's user ID is {yoshid}")
yoshid = 1019412572271611904
team_name, user_id = jmespath.search(f"[?user_id=='{yoshid}'].[metadata.team_name,user_id][0]", users)
rosters = api.rosters()
players = api.players()
yroster = jmespath.search(f"[?owner_id=='{yoshid}'].starters", rosters)[0]
yplayers = [players[player] for player in yroster]
columns=['position', 'first_name', 'last_name', 'team']
df = pd.DataFrame(yplayers, columns=columns)
print(df.to_string(index=False))
