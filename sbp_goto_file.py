#bootstrapping
plugin_path = os.path.dirname(__file__)
if not os.path.exists(os.path.join(plugin_path, 'GotoOpenFile.py')):

	# Download the file
	url = "https://raw.github.com/grundprinzip/sublime-goto-open-file/d86ed0230d56d5f6309c7ab6af1ca81c760edc5c/GotoOpenFile.py"
	crc = "4b54d7c5ff90066e8bc3b414be2bcf55"
	
	import urllib
	from hashlib import md5

	payload = urllib.urlopen(url).read()
    if md5(payload).hexdigest() != crc:
        raise ImportError('Invalid checksum.')


     # Open file to write result
     fid = open(os.path.join(plugin_path, "GotoOpenFile.py"), "w+")
     fid.write(payload)
     fid.close

# end bootstrap

import GotoOpenFile