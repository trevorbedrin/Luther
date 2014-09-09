import sys
import re
import urllib2
import scraper
from bs4 import BeautifulSoup
import dateutil.parser
import urlparse
import operator
import unicodedata
from pprint import pprint
import pickle

class BOMojoScraper(scraper.Scraper):

    base_url = "http://www.boxofficemojo.com/"
    search_url = base_url + "search/?q=%s"
    
    def build_movie_database(self, movie_name_file):
    	database_list = []
    	with open(movie_name_file, 'r') as file:
    		movie_names = file.readlines()
    		
    	print "Building database."

    	movie_names = [x.strip('\n') for x in movie_names]
    	for movie_name in movie_names:
    		print "Processing ", movie_name
    		try:
    			movie_dict = self.full_movie_dict_from_title(movie_name)
    			if movie_dict != False:
    				database_list.append(movie_dict)
    		except: 
    			print "Error Processing ", movie_name
    	with open('database_file', 'w') as pickle_file:
    		pickle.dump(database_list, pickle_file) 
    	print "Database completed."
    
    def get_full_movie_list(self):
        all_movies = []
        url_list = []
        url = self.base_url + "movies/"
        soup = self.connect(url)
        for letter in soup.find(text=re.compile('ALPHABETICAL INDEX')).parent.parent.parent.parent.findNextSibling().find_all('a', href=True):
            letter_url = self.base_url + "movies/" + letter['href']
            url_list.append(letter_url)
            letter_soup = self.connect(letter_url)
            for sub_letter_soup in letter_soup.find(class_='alpha-nav-holder').find_all('a', href=True):
                sub_letter_url = self.base_url + sub_letter_soup['href'][1:]
                url_list.append(sub_letter_url)
        for current_url in url_list:
        	print "Processing %s" % current_url
        	all_movies.append(self.scrape_sub_letter_page(current_url))

        all_movies = reduce(operator.add, all_movies)
        
        with open('all_movies.csv', 'w') as movie_file:   
        	print "Adding items to file."     
        	for item in all_movies:
        	 	movie_file.write("%s\n" % item.replace(u'\xa0', ' ').encode('utf-8'))
        
        print len(all_movies), " found."
        
    def scrape_sub_letter_page(self, url):
    	return_list = []
        soup = self.connect(url)
        #for table_row in soup.find(text='Title (click to view box office)').findParent('table').find_all('tr'):
        #	print table_row
        anchor_list = soup.find_all('a')
        for anchor in anchor_list:
        	if re.compile('\/movies\/\?id=.*\.htm').match(anchor['href']):
        		return_list.append(anchor.text)
        return return_list[1:]
        				
    def full_movie_dict_from_title(self,movie_name):
        return self.parse_full_mojo_page(self.get_full_page_url_from_title(movie_name))

    def get_full_page_url_from_title(self,movie_name):
        search_soup = self.search(movie_name.replace('(', '').replace(')', '').replace(':', ''))
        #search_soup = self.search(movie_name)
        found_matches = search_soup.find(text=re.compile("Movie Matches"))
        if found_matches:
            matches_table = found_matches.parent.find_next_sibling("table")
            rows = matches_table.find_all('tr')
            if len(rows) == 2:
            	result_row = rows[1]
            	full_page_url = urlparse.urljoin(self.base_url,result_row.find('a')['href'])
            	return full_page_url
            else: 
            	return -1

        # if we end up here without returning anything, we did not hit a match
        log_message = "[LOG: No match found for %s]" % movie_name
        print >> sys.stderr, log_message
        return -1


    def parse_full_mojo_page(self,full_page_url):
    	if full_page_url == -1:
    		return {}
    	else:
        	soup = self.connect(full_page_url)

        	if self.get_movie_value(soup,'Release Date') is not None and self.get_movie_value(soup,'Release Date') != "N/A" and self.get_movie_value(soup,'Release Date') != "TBD":
        		release_date = self.to_date(self.get_movie_value(soup,'Release Date'))
        	else:
        		release_date = None
        	if self.get_movie_value(soup,'Domestic Total Gross') is not None and self.get_movie_value(soup,'Domestic Total Gross') != "N/A":
        		domestic_total_gross = self.money_to_int(self.get_movie_value(soup,'Domestic Total Gross'))
        	else:
        		domestic_total_gross = None
        	if self.get_movie_value(soup,'Runtime') is not None and self.get_movie_value(soup,'Runtime') != "N/A":
        		runtime = self.runtime_to_minutes(self.get_movie_value(soup,'Runtime'))
        	else:
        		runtime = None
        	if self.get_movie_value(soup,'Director') is not None and self.get_movie_value(soup,'Director') != "N/A":
        		director = self.get_movie_value(soup,'Director')
        	else:
        		director = None
        	if self.get_movie_value(soup,'MPAA Rating') is not None and self.get_movie_value(soup,'MPAA Rating') != "N/A":
        		rating = self.get_movie_value(soup,'MPAA Rating')
        	else:
        		rating = None

        	movie_dict = {
            	'movie title':self.get_movie_title(soup),
            	'release date':release_date,
            	'domestic_total_gross':domestic_total_gross,
            	'runtime':runtime,
            	'director':director,
            	'rating':rating
        	}

        	return movie_dict
            

    def get_movie_value(self,soup,value_name):
        '''
        takes a string attribute of a movie on the page and 
        returns the string in the next sibling object (the value for that attribute)
        '''
        obj = soup.find(text=re.compile(value_name))
        if not obj: 
            return None
    
        # this works for most of the values
        next_sibling = obj.findNextSibling()
        if next_sibling:
            return next_sibling.text

        # this next part works for the director
        elif obj.find_parent('td'):
            sibling_cell = obj.find_parent('tr')
            if sibling_cell is not None and sibling_cell.findNextSibling() is not None:
            	sibling_cell = sibling_cell.findNextSibling()
            if sibling_cell:
                return sibling_cell.text
        
        else:
            return -1


    def get_movie_title(self,soup):
        title_tag = soup.find('title')
        movie_title = title_tag.text.split('(')[0].strip()
        return movie_title
    
    def to_date(self,datestring):
        return dateutil.parser.parse(datestring)

    def money_to_int(self,moneystring):
        return int(moneystring.replace('$','').replace(',',''))

    def runtime_to_minutes(self,runtimestring):
        rt = runtimestring.split(' ')
        return int(rt[0])*60 + int(rt[2])
