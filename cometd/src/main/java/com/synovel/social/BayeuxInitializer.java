
package com.synovel.social;

import java.io.IOException;

import javax.servlet.GenericServlet;
import javax.servlet.ServletException;
import javax.servlet.ServletRequest;
import javax.servlet.ServletResponse;

import org.cometd.bayeux.server.BayeuxServer;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class BayeuxInitializer extends GenericServlet
{
	private static final long serialVersionUID = 3001025220864808334L;
	private static Logger logger;

    public void init() throws ServletException {
        logger = LoggerFactory.getLogger(getClass().getName());
        logger.debug("Initializing Bayeux Server");

        BayeuxServer bayeux = (BayeuxServer)getServletContext().getAttribute(BayeuxServer.ATTRIBUTE);
        BayeuxAuthenticator authenticator = new BayeuxAuthenticator();
        bayeux.setSecurityPolicy(authenticator);
    }

    public void service(ServletRequest request, ServletResponse response) throws ServletException, IOException {
    }
}
