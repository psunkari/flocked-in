#
# Move the latest source from "src" to "deploy"
# and restart the application
#

cur_dir=`pwd` && cd $HOME

tar -xjf upload.tar.bz2 || exit 1

if [ -f deploy/twistd.pid ]; then
  pid=`cat deploy/twistd.pid` && kill $pid
fi

# Remove existing code
rm -rf deploy

# Copy new code
mv src deploy

# Start twisted daemon
cd deploy && twistd -y social.tac
cd $cur_dir
