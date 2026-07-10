import asyncio
import sys
import os

# Add custom_components to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'custom_components')))

# We need to mock aiohttp and home assistant core enough to run api.py
# Or better yet, we can just use the api.py which is built on aiohttp client session.
from tuya_smart_hc.api import TuyaCloudApi

async def test():
    import aiohttp
    async with aiohttp.ClientSession() as session:
        api = TuyaCloudApi(
            "congtuhaixinhzai@gmail.com",
            "Hajchjp97!",
            "84", # Vietnam country code
            "smart_life" # app type
        )
        api._session = session # inject session if needed? No, api might use async_get_clientsession
        
        # In HA, api uses helpers to get session, which will fail if not in HA.
        # Let's mock it
        def mock_get_session(hass):
            return session
            
        import tuya_smart_hc.api as api_module
        api_module.async_get_clientsession = mock_get_session
        
        # We also need to mock hass object passed to TuyaCloudApi
        class MockHass:
            pass
            
        api.hass = MockHass()
        
        try:
            print("Connecting...")
            result = await api.async_connect()
            print("Login result:", result)
            
            print("Fetching devices...")
            devices = await api.async_devices()
            print("Devices found:", len(devices))
        except Exception as e:
            print("Error:", e)

asyncio.run(test())
