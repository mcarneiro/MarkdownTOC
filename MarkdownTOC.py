import sublime
import sublime_plugin
import re
import os.path

pattern_endspace = re.compile(r' *?\z')

pattern_h1_h2_equal_dash = "^.*?(?:(?:\r\n)|\n|\r)(?:-+|=+)$"

TOCTAG_REGEX_START = "^<!-- MarkdownTOC"
TOCTAG_END = "<!-- /MarkdownTOC -->"


class MarkdowntocInsert(sublime_plugin.TextCommand):

    def run(self, edit):

        if not self.find_tag_and_insert(edit):
            sels = self.view.sel()
            for sel in sels:

                # add TOCTAG
                toc = "<!-- MarkdownTOC -->\n"
                toc += "\n"
                toc += self.getTOC(self.get_default_depth(), sel.end(), self.get_is_multi_markdown())
                toc += "\n"
                toc += TOCTAG_END + "\n"

                self.view.insert(edit, sel.begin(), toc)

        # TODO: process to add another toc when tag exists

    # get inline attributes on the MarkdownTOC comment
    def get_file_attr(self):
        depthExtractions = []
        self.depth = self.get_default_depth()
        self.view.find_all(
            TOCTAG_REGEX_START + ".*?depth=(\d+)",
            sublime.IGNORECASE, '$1', depthExtractions)
        if 0 < len(depthExtractions) and str(depthExtractions[0]) != '':
            self.depth = int(depthExtractions[0])

        multiMarkdownExtractions = []
        self.is_multi_markdown = self.get_is_multi_markdown()
        self.view.find_all(
            TOCTAG_REGEX_START + ".*?is_multi_markdown=(true|false)",
            sublime.IGNORECASE, '$1', multiMarkdownExtractions)
        if 0 < len(multiMarkdownExtractions) and str(multiMarkdownExtractions[0]) != '':
            self.is_multi_markdown = multiMarkdownExtractions[0].lower() == "true";

    # Search MarkdownTOC comments in document
    def find_tag_and_insert(self, edit):
        sublime.status_message('fint TOC tags and refresh its content')


        toc_starts = self.view.find_all(
            TOCTAG_REGEX_START + ".*? -->\n",
            sublime.IGNORECASE)

        self.get_file_attr()

        for toc_start in toc_starts:
            if 0 < len(toc_start):
                toc_end = self.view.find(
                    "^" + TOCTAG_END + "\n", toc_start.end())
                if toc_end:
                    toc = self.getTOC(self.depth, toc_end.end(), self.is_multi_markdown)
                    tocRegion = sublime.Region(
                        toc_start.end(), toc_end.begin())
                    if toc:
                        self.view.replace(edit, tocRegion, "\n" + toc + "\n")
                        sublime.status_message('find TOC-tags and refresh')
                        return True
                    else:
                        self.view.replace(edit, tocRegion, "\n")
                        return False

        # self.view.status_message('no TOC-tags')
        return False

    # TODO: add "end" parameter
    def getTOC(self, depth=0, begin=0, is_multi_markdown=True):

        # set anchor pattern
        if is_multi_markdown:
            pattern_anchor = re.compile(r'\[(.*?)\]')
        else:
            pattern_anchor = re.compile(r'<a name="(.*?)"></a>')

        # Search headings in docment
        if depth == 0:
            pattern_hash = "^#+?[^#]"
        else:
            pattern_hash = "^#{1," + str(depth) + "}[^#]"
        headings = self.view.find_all(
            "%s|%s" % (pattern_h1_h2_equal_dash, pattern_hash))

        # -----------------------------------
        # Ignore comments inside code blocks
        
        codeblocks = self.view.find_all("^`{3,}[^`]*$")
        codeblockAreas = [] # [[area_begin, area_end], ..]
        i = 0
        while i < len(codeblocks)-1:
            area_begin = codeblocks[i].begin()
            area_end   = codeblocks[i+1].begin()
            if area_begin and area_end:
                codeblockAreas.append([area_begin, area_end])
            i += 2

        headings = [h for h in headings if isOutOfAreas(h.begin(), codeblockAreas)]

        # -----------------------------------

        if len(headings) < 1:
            return False

        items = []  # [[headingNum,text],...]
        for heading in headings:
            if begin < heading.end():
                lines = self.view.lines(heading)
                if len(lines) == 1:
                    # handle hash headings, ### chapter 1
                    r = sublime.Region(
                        heading.end(), self.view.line(heading).end())
                    heading_text = self.view.substr(r)
                    heading_num = heading.size() - 1
                    items.append([heading_num, heading_text])
                elif len(lines) == 2:
                    # handle - or + headings, Title 1==== section1----
                    heading_text = self.view.substr(lines[0])
                    if heading_text.strip():
                        heading_num = 1 if (
                            self.view.substr(lines[1])[0] == '=') else 2
                        items.append([heading_num, heading_text])
        
        if len(items) < 1:
            return
        # Shape TOC  ------------------
        items = format(items)

        # Create TOC  ------------------
        toc = ''
        for item in items:
            heading_num = item[0] - 1
            heading_text = item[1].rstrip()

            # add indent by heading_num
            for i in range(heading_num):
                toc += '\t'

            # Handling anchors ("Reference-style links")
            matchObj = pattern_anchor.search(heading_text)
            if matchObj:
                only_text = heading_text[0:matchObj.start()]
                only_text = only_text.rstrip()
                id_text = matchObj.group(1)
                toc += '- [' + only_text + '](#' + id_text + ')\n'
            else:
                toc += '- ' + heading_text + '\n'

        return toc

    def get_default_depth(self):
        default_depth = self.get_setting('default_depth')
        if default_depth is None:
            default_depth = 2
            self.set_setting('default_depth', default_depth)
        return default_depth

    def get_is_multi_markdown(self):
        is_multi_markdown = self.get_setting('is_multi_markdown')
        if is_multi_markdown is None:
            is_multi_markdown = False
            self.set_setting('is_multi_markdown', is_multi_markdown)
        return is_multi_markdown

    def get_setting(self, name):
        settings = sublime.load_settings('MarkdownTOC.sublime-settings')
        return settings.get(name)

    def set_setting(self, name, value):
        # Save "Settings - Default"
        setting_file = 'MarkdownTOC.sublime-settings'
        settings = sublime.load_settings(setting_file)
        settings.set(name, value)
        sublime.save_settings(setting_file)

def isOutOfAreas(num, areas):
    for area in areas:
        if area[0] < num and num < area[1]:
            return False
    return True

def format(items):
    headings = []
    for item in items:
        headings.append(item[0])
    # ----------

    # set root to 1
    min_heading = min(headings)
    if 1 < min_heading:
        for i, item in enumerate(headings):
            headings[i] -= min_heading - 1
    headings[0] = 1  # first item must be 1

    # minimize "jump width"
    for i, item in enumerate(headings):
        if 0 < i and 1 < item - headings[i - 1]:
            before = headings[i]
            after = headings[i - 1] + 1
            headings[i] = after
            for n in range(i + 1, len(headings)):
                if(headings[n] == before):
                    headings[n] = after
                else:
                    break

    # ----------
    for i, item in enumerate(items):
        item[0] = headings[i]
    return items

# Search and refresh if it's exist


class MarkdowntocUpdate(MarkdowntocInsert):

    def run(self, edit):
        MarkdowntocInsert.find_tag_and_insert(self, edit)


class AutoRunner(sublime_plugin.EventListener):

    def on_pre_save(self, view):
        # limit scope
        root, ext = os.path.splitext(view.file_name())
        ext = ext.lower()
        if ext in [".md", ".markdown", ".mdown", ".mdwn", ".mkdn", ".mkd", ".mark"]:
            view.run_command('markdowntoc_update')
