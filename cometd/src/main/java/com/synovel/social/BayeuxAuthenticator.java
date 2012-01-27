
package com.synovel.social;

import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.Cookie;

import org.cometd.bayeux.ChannelId;
import org.cometd.bayeux.server.BayeuxServer;
import org.cometd.bayeux.server.ServerChannel;
import org.cometd.bayeux.server.ServerMessage;
import org.cometd.bayeux.server.ServerSession;
import org.cometd.server.DefaultSecurityPolicy;
import org.cometd.server.transport.HttpTransport;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Properties;
import java.lang.Exception;

public class BayeuxAuthenticator extends DefaultSecurityPolicy implements ServerSession.RemoveListener
{
    private static String sessionCookieName = "session";
    private final Logger logger;
    private final SocialConnector connector = new SocialConnector();

    public BayeuxAuthenticator() {
        logger = LoggerFactory.getLogger(getClass().getName());

        Properties p = new Properties();
        try {
          p.load( this.getClass().getResourceAsStream("/social.properties") );
        } catch (Exception ex) {
        }

    	logger.debug("url property: " + p.getProperty("base.url"));
    }

    private String getCookie(BayeuxServer server, String name) {
        HttpTransport transport = (HttpTransport)server.getCurrentTransport();
        HttpServletRequest request = transport.getCurrentRequest();

        String cookie = null;
        Cookie[] cookies = request.getCookies();
        if (cookies != null)
        {
            for (Cookie c: cookies)
            {
                if (name.equals(c.getName()))
                    cookie = c.getValue();
            }
        }
        return cookie;
    }

    @Override
    public boolean canCreate(BayeuxServer server, ServerSession session, String channelId, ServerMessage message) {
    	logger.debug("Trying to create a channel");
        return session!=null && session.isLocalSession() || !ChannelId.isMeta(channelId);
    }

    @Override
    public boolean canHandshake(BayeuxServer server, ServerSession session, ServerMessage message) {
    	logger.debug("Trying to handshake with the server");
        if (session!=null && session.isLocalSession())
        	return true;

    	String appSessionId = getCookie(server, sessionCookieName);
        
        try {
        	logger.debug("Trying to validate authenticate session: " + appSessionId);
        	SocialConnector.AuthData auth = connector.validateSession(appSessionId);
        	session.setAttribute("appSessionId", appSessionId);
        	session.setAttribute("auth", auth);
        	
        	return true;
        } catch(Exception ex) {
        	logger.debug(ex.toString());
        	return false;
        }
    }

    @Override
    public boolean canPublish(BayeuxServer server, ServerSession session, ServerChannel channel, ServerMessage message) {
    	logger.debug("Trying to publish data");
        if (session!=null && session.isLocalSession())
        	return true;

        if (ChannelId.isMeta(channel.getId()))
    		return false;
        
        try {
        	String appSessionId = (String) session.getAttribute("appSessionId");
        	logger.debug("Trying to validate publish to channel: " + channel.getId() + " to session: " + appSessionId);
        	SocialConnector.ResultData resultData = connector.validateSubscribe(appSessionId, channel.getId());
        	
        	if (resultData.isSuccess())
        		return true;
        	else {
        		logger.debug("Not authorized to publish. Reason: " + resultData.reason);
                return false;
        	}

        } catch(Exception ex) {
        	logger.debug(ex.toString());
        	return false;
        }
    }

    @Override
    public boolean canSubscribe(BayeuxServer server, ServerSession session, ServerChannel channel, ServerMessage message) {
    	logger.debug("Trying to subscribe to a channel");
        if (session!=null && session.isLocalSession())
        	return true;
    	
    	if (ChannelId.isMeta(channel.getId()))
    		return false;
    		
        try {
        	String appSessionId = (String) session.getAttribute("appSessionId");
        	logger.debug("Trying to validate subscription to channel: " + channel.getId() + " to session: " + appSessionId);
        	SocialConnector.ResultData resultData = connector.validateSubscribe(appSessionId, channel.getId());
        	
        	if (resultData.isSuccess())
        		return true;
        	else {
        		logger.debug("Not authorized to subscribe. Reason: " + resultData.reason);
                return false;
        	}

        } catch(Exception ex) {
        	logger.debug(ex.toString());
        	return false;
        }
    }

    public void removed(ServerSession session, boolean timeout) {
        try {
        	String appSessionId = (String) session.getAttribute("appSessionId");
        	SocialConnector.AuthData auth = (SocialConnector.AuthData) session.getAttribute("auth");
        	
        	logger.debug("Trying to remove session: " + appSessionId + " of userid: " + auth.user);
        	connector.removeSession(appSessionId, auth.user);        	
        } catch(Exception ex) {
        	logger.debug(ex.toString());
        }
    }
}
