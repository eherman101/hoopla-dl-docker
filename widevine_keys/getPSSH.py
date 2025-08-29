import requests
import xmltodict
import json

def get_pssh(mpd_url):
    pssh = ''
    try:
        r = requests.get(url=mpd_url)
        r.raise_for_status()
        xml = xmltodict.parse(r.text)
        mpd = json.loads(json.dumps(xml))
        periods = mpd['MPD']['Period']
        
        namespace = {'mpd_ns': 'urn:mpeg:dash:schema:mpd:2011'}

        for period in periods if isinstance(periods, list) else [periods]:
            adaptation_sets = period.get('AdaptationSet', [])
            if not isinstance(adaptation_sets, list):
                adaptation_sets = [adaptation_sets]

            for ad_set in adaptation_sets:
                if ad_set.get('@mimeType') == 'audio/mp4':
                    content_protections = ad_set.get('ContentProtection', [])
                    if not isinstance(content_protections, list):
                        content_protections = [content_protections]

                    for cp in content_protections:
                        scheme_id_uri = cp.get('@schemeIdUri', '').lower()
                        if scheme_id_uri == "urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed":
                            pssh = cp.get('cenc:pssh', '')

    except Exception as e:
        pssh = input(f'\nUnable to find PSSH in MPD: {e}. \nEdit getPSSH.py or enter PSSH manually: ')

    if pssh == '':
        pssh = input('Unable to find PSSH in mpd. Edit getPSSH.py or enter PSSH manually: ')

    return pssh