package com.synovel.social;

import com.google.api.client.http.HttpTransport;
import com.google.api.client.http.javanet.NetHttpTransport;
import com.google.api.client.http.GenericUrl;
import com.google.api.client.http.HttpRequest;
import com.google.api.client.http.HttpRequestFactory;
import com.google.api.client.http.HttpRequestInitializer;
import com.google.api.client.json.JsonFactory;
import com.google.api.client.json.jackson.JacksonFactory;
import com.google.api.client.http.json.JsonHttpParser;
import com.google.api.client.util.Key;

public class SessionValidator
{
	static final HttpTransport HTTP_TRANSPORT = new NetHttpTransport();
	static final JsonFactory JSON_FACTORY = new JacksonFactory();
	static final String SHARED_SECRET = "ABCDE";

	public static class AuthData {
		@Key
		public String user;		
		@Key
		public String org;
	}
		
	public AuthData run(String appSessionId) throws Exception {
		if (appSessionId.equals(SHARED_SECRET)) {
			AuthData authData = new AuthData();
			authData.user = "server";
			authData.org = "server";
			return authData;
		}

		HttpRequestFactory requestFactory = 
				HTTP_TRANSPORT.createRequestFactory(new HttpRequestInitializer() {
					public void initialize(HttpRequest request) {
						request.addParser(new JsonHttpParser(JSON_FACTORY));
					}
				});
		HttpRequest request = requestFactory.buildGetRequest(
				new GenericUrl("http://localhost/private/validate-session?id="+appSessionId));
		return request.execute().parseAs(AuthData.class);
	}
}
