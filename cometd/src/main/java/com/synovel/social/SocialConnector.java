package com.synovel.social;

import java.io.IOException;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import com.google.api.client.http.HttpTransport;
import com.google.api.client.http.javanet.NetHttpTransport;
import com.google.api.client.http.GenericUrl;
import com.google.api.client.http.HttpRequest;
import com.google.api.client.http.HttpRequestFactory;
import com.google.api.client.http.HttpRequestInitializer;
import com.google.api.client.http.HttpResponseException;
import com.google.api.client.json.JsonFactory;
import com.google.api.client.json.jackson.JacksonFactory;
import com.google.api.client.http.json.JsonHttpParser;
import com.google.api.client.util.Key;

public class SocialConnector
{
	static final HttpTransport HTTP_TRANSPORT = new NetHttpTransport();
	static final JsonFactory JSON_FACTORY = new JacksonFactory();
	static final String SHARED_SECRET = "ABCDE";

	private final Logger logger;
	
	static final String _baseUrl 				= "http://192.168.36.101:8888/private/";
	static final String _sessionUrlFormat 		= _baseUrl + "validate-session?sessionid=%s";
	static final String _subscribeUrlFormat 	= _baseUrl + "is-authorized?sessionid=%s&channelid=";
	static final String _publishUrlFormat 		= _baseUrl + "validate-session?sessionid=%s&channeid=%s";
	static final String _disconnectUrlFormat 	= _baseUrl + "disconnnect?sessionid=%s&userid=%s";

	public static class AuthData {
		@Key
		public String user;		
		@Key
		public String org;
	}
	
	public static class ResultData {
		@Key
		public String status;
		@Key
		public String reason;
		
		public boolean isSuccess() {
			return status.equals("SUCCESS");
		}
	}
	
	public SocialConnector() {
		logger = LoggerFactory.getLogger(getClass().getName());
	}
	
	public AuthData validateSession(String appSessionId) throws IOException {
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
		
		String url = String.format(_sessionUrlFormat, appSessionId);
		HttpRequest request = requestFactory.buildGetRequest(new GenericUrl(url));
		
		return request.execute().parseAs(AuthData.class);
	}
	
	public ResultData validateSubscribe(String appSessionId, String channelId) throws IOException {
		if (appSessionId.equals(SHARED_SECRET)) {
			ResultData resultData = new ResultData();
			resultData.status = "SUCCESS";
			resultData.reason = "Passed with shared secret";
			return resultData;
		}
		
		HttpRequestFactory requestFactory = 
			HTTP_TRANSPORT.createRequestFactory(new HttpRequestInitializer() {
				public void initialize(HttpRequest request) {
					request.addParser(new JsonHttpParser(JSON_FACTORY));
				}
			});
		
		String url = String.format(_subscribeUrlFormat, appSessionId, channelId);
		HttpRequest request = requestFactory.buildGetRequest(new GenericUrl(url));
		
		try {
			return request.execute().parseAs(ResultData.class);
		} catch (HttpResponseException ex) {
			ResultData resultData = ex.getResponse().parseAs(ResultData.class);
			logger.debug("SocialConnector request failed. Reason: " + resultData.reason);
			throw ex;
		}
	}
	
	public ResultData validatePublish(String appSessionId, String channelId) throws IOException {
		ResultData resultData = new ResultData();
		resultData.status = "FAILURE";
		resultData.reason = "Only apps with shared secret can publish";
		
		if (appSessionId.equals(SHARED_SECRET)) {
			resultData.status = "SUCCESS";
			resultData.reason = "Passed with shared secret";
		}
		
		return resultData;
		
	}
	
	public void removeSession(String appSessionId, String channelId) throws IOException {
		
		HttpRequestFactory requestFactory = 
			HTTP_TRANSPORT.createRequestFactory(new HttpRequestInitializer() {
				public void initialize(HttpRequest request) {
					request.addParser(new JsonHttpParser(JSON_FACTORY));
				}
			});
		
		String url = String.format(_disconnectUrlFormat, appSessionId, channelId);
		HttpRequest request = requestFactory.buildGetRequest(new GenericUrl(url));
		
		request.execute();
	}
}
