from tokenstuff import *
from msal import PublicClientApplication

def refreshtoken(refresh_token):
    client_id = "9be57e9e-4bf2-4251-bb3c-0298d2bdda0a"
    scopes = ["XboxLive.signin"]
    authority = "https://login.microsoftonline.com/consumers"

    pca = PublicClientApplication(client_id, authority=authority)

    # Acquire a new access token using the refresh token
    result = pca.acquire_token_by_refresh_token(refresh_token, scopes=scopes)

    if "access_token" in result:
        new_access_token = result["access_token"]
        new_refresh_token = result["refresh_token"]
            
        newxbl3token = getxbl3(new_access_token)

        print(newxbl3token)
    else:
        print("An error occurred while refreshing the token.")