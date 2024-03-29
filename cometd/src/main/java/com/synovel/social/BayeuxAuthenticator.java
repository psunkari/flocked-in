
package com.synovel.social;

import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.Cookie;
import java.util.HashSet;
import java.util.HashMap;

import org.cometd.bayeux.ChannelId;
import org.cometd.bayeux.server.BayeuxServer;
import org.cometd.bayeux.server.ServerChannel;
import org.cometd.bayeux.server.ServerMessage;
import org.cometd.bayeux.server.ServerSession;
import org.cometd.server.DefaultSecurityPolicy;
import org.cometd.server.transport.HttpTransport;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import com.synovel.social.SocialConnector.AuthData;
import com.synovel.social.SocialConnector.ResultData;

import java.io.IOException;

public class BayeuxAuthenticator extends DefaultSecurityPolicy implements ServerSession.RemoveListener
{
    private static String sessionCookieName = "session";
    private final Logger logger;
    private final SocialConnector connector = new SocialConnector();

    private final HashMap<String, HashSet> sessions2clients = new HashMap<String, HashSet>();

    public BayeuxAuthenticator() {
        logger = LoggerFactory.getLogger(getClass().getName());
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

    private synchronized int updateClientToSession(String appSessionId, String clientId, boolean remove) {
        HashSet<String> clients;
        int size = 0;

        if (remove) {
            if (sessions2clients.containsKey(appSessionId)) {
                clients = sessions2clients.get(appSessionId);
                clients.remove(clientId);
                size = clients.size();
                if (size == 0)
                    sessions2clients.remove(appSessionId);
            }
        } else {
            if (!sessions2clients.containsKey(appSessionId)) {
                clients = new HashSet<String>();
                sessions2clients.put(appSessionId, clients);
            } else {
                clients = sessions2clients.get(appSessionId);
            }
            clients.add(clientId);
            size = clients.size();
        }

        return size;
    }

    @Override
    public boolean canHandshake(BayeuxServer server, ServerSession session, ServerMessage message) {
        logger.debug("Trying to handshake with the server");
        if (session!=null && session.isLocalSession())
            return true;

        String appSessionId = getCookie(server, sessionCookieName);
        if (appSessionId == null)
            return false;

        try {
            logger.debug("Trying to validate authenticate session: " + appSessionId);
            AuthData auth = connector.validateSession(appSessionId);
            session.setAttribute("appSessionId", appSessionId);
            session.setAttribute("auth", auth);

            // If handshake is successful, add remove listener to cleanup when connection closes
            session.addListener(this);
            updateClientToSession(appSessionId, session.getId(), false);

            return true;
        } catch(IOException ex) {
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
            ResultData resultData = connector.validatePublish(appSessionId, channel.getId());

            if (resultData.status)
                return true;
            else {
                logger.debug("Not authorized to publish. Reason: " + resultData.reason);
                return false;
            }

        } catch(IOException ex) {
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
            AuthData authData = (AuthData) session.getAttribute("auth");

            logger.debug("Trying to validate subscription to channel: " + channel.getId() +
                         " to session: " + appSessionId + ", user: " + authData.user + ", org: " + authData.org);
            ResultData resultData = connector.validateSubscribe(appSessionId, channel.getId(), authData.user, authData.org);

            if (resultData.status)
                return true;
            else {
                logger.debug("Not authorized to subscribe. Reason: " + resultData.reason);
                return false;
            }

        } catch(IOException ex) {
            logger.debug(ex.toString());
            return false;
        }
    }

    public void removed(ServerSession session, boolean timeout) {
        int clientCount;

        try {
            String appSessionId = (String) session.getAttribute("appSessionId");
            logger.debug("Trying to remove session: " + appSessionId);

            clientCount = updateClientToSession(appSessionId, session.getId(), true);
            if (clientCount == 0)
                connector.removeSession(appSessionId);
        } catch(IOException ex) {
            logger.debug(ex.toString());
        }
    }
}
