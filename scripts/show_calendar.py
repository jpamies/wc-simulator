import json
cal = json.load(open('data/tournament/calendar.json', 'r', encoding='utf-8'))
for md in cal:
    print(f"{md['id']:6s} {md['phase']:8s} {md['name']:40s} {len(md['matches'])} matches")
    # Show FINAL matches detail
    if md['id'] == 'FINAL':
        for m in md['matches']:
            print(f"  M{m['match_number']}: {m['home']} vs {m['away']} @ {m['kickoff']}")
