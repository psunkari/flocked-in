
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
    	String appSessionId = getCookie(server, sessionCookieName);
        SessionValidator validator = new SessionValidator();
        try {
        	SessionValidator.AuthData auth = validator.run(appSessionId);
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
    	return true;
        //return session!=null && session.isHandshook() && !channel.isMeta();
    }

    @Override
    public boolean canSubscribe(BayeuxServer server, ServerSession session, ServerChannel channel, ServerMessage message) {
    	logger.debug("Trying to subscribe to a channel");
        return session!=null && session.isLocalSession() || !channel.isMeta();
    }

    public void removed(ServerSession session, boolean timeout) {
    }
}
