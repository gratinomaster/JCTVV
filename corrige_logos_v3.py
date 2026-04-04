#!/usr/bin/env python3
import re

with open("lista5.m3u", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace('tvg-logo="https://raw.githubusercontent.com/LITUATUI/M3UPT/main/logos/TRT_World.jpg",Fox News', 'tvg-logo="https://upload.wikimedia.org/wikipedia/commons/thumb/6/67/Fox_News_Channel_logo.svg/512px-Fox_News_Channel_logo.svg.jpg",Fox News')

content = content.replace('tvg-logo="https://raw.githubusercontent.com/LITUATUI/M3UPT/main/logos/TRT_World.jpg",Free Speech TV', 'tvg-logo="https://raw.githubusercontent.com/LITUATUI/M3UPT/main/logos/Free-Speech-TV.jpg",Free Speech TV')

content = content.replace('tvg-logo="https://www.ntd.com/images/ENTD180.jpg",NTD News', 'tvg-logo="https://raw.githubusercontent.com/LITUATUI/M3UPT/main/logos/NTD.jpg",NTD News')

content = content.replace('tvg-logo="https://images-3.rakuten.tv/storage/global-live-channel/translation/artwork/39a979b9-49df-48c1-8c1c-5763828b60aa-width200-quality90.jpg",Rakuten TV - Top Movies', 'tvg-logo="https://raw.githubusercontent.com/LITUATUI/M3UPT/main/logos/Rakuten-TV-Top-Movies.jpg",Rakuten TV - Top Movies')

content = content.replace('tvg-logo="https://www.lyngsat-logo.com/logo/tv/mm/macau_lotus_tv_mo.jpg",Lotus Macau', 'tvg-logo="https://raw.githubusercontent.com/LITUATUI/M3UPT/main/logos/Lotus-Macau.jpg",Lotus Macau')

content = content.replace('tvg-logo="https://assimeportugal.com/wp-content/uploads/2020/10/lg-assim.jpg",Assim é Portugal', 'tvg-logo="https://raw.githubusercontent.com/LITUATUI/M3UPT/main/logos/Assim-Portugal.jpg",Assim é Portugal')

content = content.replace('tvg-logo="https://www.rfptv.pt/storage/479/config/MYvhCGImba3MPCwmRu2pZgGkFhy2L6tkTLsSO3LN.jpg",RFPtv', 'tvg-logo="https://raw.githubusercontent.com/LITUATUI/M3UPT/main/logos/RFPtv.jpg",RFPtv')

content = content.replace('tvg-logo="https://i.ibb.co/nm0jXMM/cultura-3x.jpg",TV Cultura', 'tvg-logo="https://raw.githubusercontent.com/LITUATUI/M3UPT/main/logos/TV-Cultura.jpg",TV Cultura')

content = content.replace('tvg-logo="https://static.wikia.nocookie.net/logopedia/images/1/12/Arag%C3%B3n_Internacional.png/revision/latest/scale-to-width-down/512.jpg",Aragón TV Internacional', 'tvg-logo="https://raw.githubusercontent.com/LITUATUI/M3UPT/main/logos/Aragon-TV.jpg",Aragón TV Internacional')

content = content.replace('tvg-logo="https://do8ct5f1tsfs2.cloudfront.net/clients_logos/7246ea51ef514a518a2e5b0b3fb871a3.jpg",Canal Málaga', 'tvg-logo="https://raw.githubusercontent.com/LITUATUI/M3UPT/main/logos/Canal-Malaga.jpg",Canal Málaga')

content = content.replace('tvg-logo="https://upload.wikimedia.org/wikipedia/commons/e/eb/Azteca_Internacional_logo_2023.jpg",Azteca Internacional', 'tvg-logo="https://raw.githubusercontent.com/LITUATUI/M3UPT/main/logos/Azteca-Internacional.jpg",Azteca Internacional')

content = content.replace('tvg-logo="https://upload.wikimedia.org/wikipedia/commons/9/9c/FIFA%2B_%282025%29.svg.jpg",FIFA+', 'tvg-logo="https://raw.githubusercontent.com/LITUATUI/M3UPT/main/logos/FIFA.jpg",FIFA+')

with open("lista5.m3u", "w", encoding="utf-8") as f:
    f.write(content)

print("Logos corrigidos")

content = re.sub(r'(group-title="[^"]*") tvg-logo=', r'\1\n#tvg-logo=', content)

with open("lista5.m3u", "w", encoding="utf-8") as f:
    f.write(content)

print("Formatacao corrigida")
