import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'plugin.video.stremioelec'))
from weather import apply,condition,search,wind_direction,normalize_country,country_code
class FakeWindow:
    def __init__(self): self.values={}
    def setProperty(self,k,v): self.values[k]=v
class WeatherTest(unittest.TestCase):
    def test_search(self):
        rows=search('Perth',fetcher=lambda _:{'results':[{'name':'Perth','admin1':'Western Australia','country':'Australia','latitude':-31.95,'longitude':115.86}]})
        self.assertEqual(rows[0]['label'],'Perth, Western Australia, Australia')
    def test_australian_postcode_uses_bundled_index(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'AU.txt'
            path.write_text(
                'AU\t6000\tPerth\tWestern Australia\tWA\tVincent\t\t\t\t-31.9522\t115.8614\t4\n'
                'AU\t6000\tCity Delivery Centre\tWestern Australia\tWA\tVincent\t\t\t\t-31.9522\t115.8614\t4\n'
            )
            rows=search('6000',country='Australia (24h)',postcode_path=path,
                        fetcher=lambda _: (_ for _ in ()).throw(AssertionError('network geocoder should not be used')))
        self.assertEqual(rows[0]['label'],'Perth 6000, Western Australia, Australia')
        self.assertEqual(rows[0]['country_code'],'AU')
        self.assertAlmostEqual(rows[0]['latitude'],-31.9522)

    def test_country_filter_is_sent_for_city_search(self):
        urls=[]
        rows=search('Perth',country='Australia (24h)',
                    fetcher=lambda url:(urls.append(url) or {'results':[{
                        'name':'Perth','admin1':'Western Australia','country':'Australia',
                        'country_code':'AU','latitude':-31.95,'longitude':115.86}]}))
        self.assertIn('countryCode=AU',urls[0])
        self.assertEqual(rows[0]['label'],'Perth, Western Australia, Australia')
        self.assertEqual(normalize_country('Australia (24h)'),'Australia')
        self.assertEqual(country_code('Australia (24h)'),'AU')

    def test_forecast_payload_timezone_can_drive_kodi_region(self):
        from weather import forecast
        urls=[]
        payload=forecast(-31.9522,115.8614,fetcher=lambda url:(
            urls.append(url) or {'timezone':'Australia/Perth'}))
        self.assertEqual(payload['timezone'],'Australia/Perth')
        self.assertIn('timezone=auto',urls[0])

    def test_codes(self):
        self.assertEqual(condition(0),('Clear sky','32')); self.assertEqual(wind_direction(270),'W')
    def test_apply(self):
        p={'current':{'time':'2026-09-24T12:00','temperature_2m':20.2,'apparent_temperature':19.5,'relative_humidity_2m':60,'precipitation':0,'weather_code':2,'wind_speed_10m':18,'wind_direction_10m':270},
           'daily':{'time':['2026-09-24'],'weather_code':[2],'temperature_2m_max':[23],'temperature_2m_min':[13],'precipitation_probability_max':[10],'sunrise':['2026-09-24T06:00'],'sunset':['2026-09-24T18:00'],'wind_speed_10m_max':[25],'wind_direction_10m_dominant':[270]},
           'hourly':{'time':['2026-09-24T12:00'],'temperature_2m':[20],'apparent_temperature':[19],'relative_humidity_2m':[60],'precipitation_probability':[10],'precipitation':[0],'weather_code':[2],'wind_speed_10m':[18],'wind_direction_10m':[270]}}
        w=FakeWindow(); apply(p,'Perth',w)
        self.assertEqual(w.values['Current.Condition'],'Partly cloudy'); self.assertEqual(w.values['Day0.HighTemp'],'23')
if __name__=='__main__': unittest.main()
