import asyncio
import random
import re
from abc import ABC
from typing import List, Iterable
from src.entity.proxy_entity import ProxyEntity
from src.enum.common import ProxyCoverEnum, ProxyTypeEnum
from src.log.logger import logger
from src.spider.abs_spider import AbsSpider
from bs4 import BeautifulSoup, Tag
from pyppeteer import launch

spider_collection = {}


def spider_register(cls):
    spider_collection.update({cls.__name__: cls()})
    logger.info(f'注册{cls.__name__}')
    return cls


@spider_register
class SpiderSpysOneIP(AbsSpider, ABC):
    """
    spys.one
    http://spys.one/proxys
    """

    def __init__(self) -> None:
        super().__init__('spys.one IP代理爬虫')

    async def _scrape(self):
        addr_re = r'\d{2,3}\.\d{2,3}\.\d{2,3}\.\d{2,3}'
        addr_port_re = addr_re + r':\d{2,5}'
        countries = ['US', 'UK', 'DE', 'JP']
        browser = await launch(
            headless=False,
            handleSIGINT=False,
            handleSIGTERM=False,
            handleSIGHUP=False
        )
        page = await browser.newPage()
        if countries is None:
            await page.goto(self.get_urls()[0], {
                "waitLoad": True,
                "waitNetworkIdle": True
            })
            await asyncio.sleep(random.uniform(2, 3))
            countries = [
                await page.evaluate('(ele) => ele.innerText', ele) for ele in await
                page.xpath('//a[@href]//*[@class="spy6"]//*[@class="spy4"]')
            ]
        res = []
        for country in countries:
            result = []
            logger.info(f"Extracting proxies from Spys {country}.")
            page_url = self.get_urls()[0]
            await page.goto(f'{page_url}{country}', {
                "waitLoad": True,
                "waitNetworkIdle": True
            })
            await asyncio.sleep(self.get_interval())
            table_rows = [
                await page.evaluate('(ele) => ele.innerText', ele)
                for ele in await page.xpath('//*[contains(@class,"spy1x")]')
            ]
            for row_data in table_rows:
                if "HTTP" in row_data or "SOCK" in row_data:
                    proxy_matches = row_data.split("\t")
                    protocol = proxy_matches[1]
                    if "SOCKS5" in protocol:
                        continue
                    if "HTTPS" in protocol:
                        protocol = 'https'
                    elif "HTTP" in protocol:
                        protocol = 'http'
                    else:
                        continue
                    ip_port = proxy_matches[0]
                    proxy_cover = proxy_matches[2]
                    region = proxy_matches[3]
                    result.append(ProxyEntity(f'{protocol}://{ip_port}',
                                              source=self._name,
                                              proxy_type=self._judge_proxy_type(protocol),
                                              proxy_cover=self._judge_proxy_cover(proxy_cover),
                                              region=region))

            res.extend(result)
            await asyncio.sleep(self.get_interval())
            print(f"Extracted {len(result)} total proxies from Spys One.")
        await browser.close()
        return res

    async def crawl(self):
        logger.info(f'{self._name}开始爬取...')
        logger.info(f'_scrape_free_proxy_list_net 开始运行...')
        result = await self._scrape()
        return result

    def get_urls(self) -> List[str]:
        return ['http://spys.one/free-proxy-list/']

    # 爬太快会被封
    def get_interval(self) -> int:
        return 2

    def get_page_url(self, url, page) -> str:
        return url

    def get_encoding(self) -> str:
        return 'utf-8'

    @staticmethod
    def _judge_proxy_type(type_str: str):
        type_low = type_str.lower()
        if type_low == 'http':
            return ProxyTypeEnum.HTTP.value
        elif type_low == 'https':
            return ProxyTypeEnum.HTTPS.value
        else:
            return ProxyTypeEnum.UNKNOWN.value

    @staticmethod
    def _judge_proxy_cover(cover_str: str):
        if cover_str == 'HIA':
            return ProxyCoverEnum.HIGH_COVER.value
        elif cover_str == 'ANM':
            return ProxyCoverEnum.NORMAL_COVER.value
        else:
            return ProxyCoverEnum.UNKNOWN.value


@spider_register
class SpiderFreeProxyListIP(AbsSpider, ABC):
    """
    free-proxy-list
    https://free-proxy-list.net
    """

    def __init__(self) -> None:
        super().__init__('free-proxy-list IP代理爬虫')

    async def _scrape(self):
        browser = await launch(
            headless=False,
            handleSIGINT=False,
            handleSIGTERM=False,
            handleSIGHUP=False
        )
        page = await browser.newPage()
        await page.goto(self.get_urls()[0], {
            "waitLoad": True,
            "waitNetworkIdle": True
        })
        res = []
        while True:
            result = []
            await asyncio.sleep(self.get_interval())
            col_names = [
                await page.evaluate('(ele) => ele.innerText.toLowerCase()', ele)
                for ele in await page.xpath('//*[@id="proxylisttable"]/thead/*[@role="row"]//*[@aria-label]')
            ]
            for row in await page.xpath('//*[@id="proxylisttable"]/tbody/*[@role="row"]'):
                col_values = [
                    await page.evaluate('(ele) => ele.innerText', ele)
                    for ele in await row.xpath('./td')
                ]
                row_data = dict(zip(col_names, col_values))
                protocol = 'http'
                if row_data['https'] == 'yes':
                    protocol = 'https'
                ip = row_data['ip address\t'].replace("\t", '')
                port = row_data['port\t'].replace("\t", '')
                proxy_cover = row_data['anonymity\t'].replace("\t", '')
                region = row_data['code\t'].replace("\t", '')
                result.append(ProxyEntity(f'{protocol}://{ip}:{port}',
                                          source=self._name,
                                          proxy_type=self._judge_proxy_type(protocol),
                                          proxy_cover=self._judge_proxy_cover(proxy_cover),
                                          region=region))
            res.extend(result)
            next_button_ele = await page.xpath('//*[@class="fg-button ui-button ui-state-default next"]')
            if next_button_ele:
                await next_button_ele[0].click()
            else:
                await browser.close()
                logger.error(f"Extracted {len(result)} total proxies from free-proxy-list.net")
                return res

    async def crawl(self):
        logger.info(f'{self._name}开始爬取...')
        logger.info(f'_scrape_free_proxy_list_net 开始运行...')
        result = await self._scrape()
        return result

    def get_urls(self) -> List[str]:
        return ['https://free-proxy-list.net']

    # 爬太快会被封
    def get_interval(self) -> int:
        return 2

    def get_page_url(self, url, page) -> str:
        return url

    def get_encoding(self) -> str:
        return 'utf-8'

    @staticmethod
    def _judge_proxy_type(type_str: str):
        type_low = type_str.lower()
        if type_low == 'http':
            return ProxyTypeEnum.HTTP.value
        elif type_low == 'https':
            return ProxyTypeEnum.HTTPS.value
        else:
            return ProxyTypeEnum.UNKNOWN.value

    @staticmethod
    def _judge_proxy_cover(cover_str: str):
        if cover_str == 'elite proxy':
            return ProxyCoverEnum.HIGH_COVER.value
        elif cover_str == 'anonymous':
            return ProxyCoverEnum.NORMAL_COVER.value
        else:
            return ProxyCoverEnum.UNKNOWN.value


@spider_register
class Spider66Ip(AbsSpider):
    """
    66IP代理爬虫 刷新速度:🐌慢
    http://www.66ip.cn/
    """

    def __init__(self) -> None:
        super().__init__('66IP代理爬虫')

    def do_crawl(self, resp) -> List[ProxyEntity]:
        result = []
        soup = BeautifulSoup(resp, 'lxml')
        tr_list = soup.find('table', attrs={'width': '100%', 'bordercolor': '#6699ff'}).find_all('tr')
        for i, tr in enumerate(tr_list):
            if i == 0:
                continue
            contents = tr.contents
            ip = contents[0].text
            port = contents[1].text
            region = contents[2].text
            proxy_cover = contents[3].text
            result.append(ProxyEntity(f'http://{ip}:{port}',
                                      source=self._name,
                                      proxy_cover=self._judge_proxy_cover(proxy_cover),
                                      region=region))
        return result

    def get_urls(self) -> List[str]:
        return ['http://www.66ip.cn']

    def get_page_range(self) -> Iterable:
        return range(1, 6)

    def get_page_url(self, url, page) -> str:
        return f'{url}/{page}.html'

    def get_encoding(self) -> str:
        return 'gb2312'

    @staticmethod
    def _judge_proxy_cover(cover_str: str):
        if cover_str == '高匿代理':
            return ProxyCoverEnum.HIGH_COVER.value
        else:
            return ProxyCoverEnum.UNKNOWN.value


@spider_register
class SpiderQuanWangIp(AbsSpider):
    """
    全网IP代理爬虫 刷新速度:极快
    http://www.goubanjia.com/
    """

    def __init__(self) -> None:
        super().__init__('全网IP代理爬虫')

    def do_crawl(self, resp) -> List[ProxyEntity]:
        result = []
        soup = BeautifulSoup(resp, 'lxml')
        tr_list = soup.find('tbody').find_all('tr')
        for i, tr in enumerate(tr_list):
            tds = tr.find_all('td')
            id_and_port = tds[0]
            ip, port = self._parse_ip_and_port(id_and_port)
            proxy_cover = tds[1].text
            proxy_type = tds[2].text
            region = tds[3].contents[1].text
            supplier = tds[4].text
            result.append(ProxyEntity(f'{proxy_type.lower()}://{ip}:{port}',
                                      source=self._name,
                                      supplier=supplier,
                                      proxy_type=self._judge_proxy_type(proxy_type),
                                      proxy_cover=self._judge_proxy_cover(proxy_cover),
                                      region=region
                                      )
                          )
        return result

    def get_urls(self) -> List[str]:
        return ['http://www.goubanjia.com']

    def get_page_url(self, url, page) -> str:
        return url

    def _parse_ip_and_port(self, ip_td: Tag):
        res = []
        contents = ip_td.find_all(['div', 'span'])
        for content in contents:
            res.append(content.text)
        res.pop()
        ip = ''.join(res)

        port_tag = contents[-1]
        port_ori_str = port_tag.get('class')[1]
        # 解码真实的端口
        port = 0
        for c in port_ori_str:
            port *= 10
            port += (ord(c) - ord('A'))
        port /= 8
        port = int(port)
        return ip, str(port)

    def _judge_proxy_type(self, type_str: str):
        type_low = type_str.lower()
        if type_low == 'http':
            return ProxyTypeEnum.HTTP.value
        elif type_low == 'https':
            return ProxyTypeEnum.HTTPS.value
        else:
            return ProxyTypeEnum.UNKNOWN.value

    def _judge_proxy_cover(self, cover_str: str):
        if cover_str == '透明':
            return ProxyCoverEnum.TRANSPARENT.value
        elif cover_str == '高匿':
            return ProxyCoverEnum.HIGH_COVER.value
        else:
            return ProxyCoverEnum.UNKNOWN.value


@spider_register
class SpiderXiciIp(AbsSpider):
    """
    西刺代理爬虫 刷新速度:🐌慢
    基本上没几个代理个能用🆒
    https://www.xicidaili.com/
    """

    def __init__(self) -> None:
        super().__init__('西刺IP代理爬虫')

    def do_crawl(self, resp) -> List[ProxyEntity]:
        result = []
        soup = BeautifulSoup(resp, 'lxml')
        tab = soup.find('table', attrs={'id': 'ip_list'})
        if tab is None:
            return []
        tr_list = tab.find_all('tr')[1: -1]
        for tr in tr_list:
            tds = tr.find_all('td')
            ip = tds[1].text
            port = tds[2].text
            proxy_cover = tds[4].text
            proxy_type = tds[5].text
            result.append(ProxyEntity(f'{proxy_type.lower()}://{ip}:{port}',
                                      source=self._name,
                                      proxy_cover=self._judge_proxy_cover(proxy_cover),
                                      proxy_type=self._judge_proxy_type(proxy_type),
                                      ))
        return result

    def get_urls(self) -> List[str]:
        return [
            'https://www.xicidaili.com/nn',  # 高匿
            'https://www.xicidaili.com/nt'  # 透明
        ]

    def get_page_range(self) -> Iterable:
        return range(1, 3)

    @staticmethod
    def _judge_proxy_cover(cover_str: str):
        if cover_str == '高匿':
            return ProxyCoverEnum.HIGH_COVER.value
        if cover_str == '透明':
            return ProxyCoverEnum.TRANSPARENT.value
        else:
            return ProxyCoverEnum.UNKNOWN.value

    @staticmethod
    def _judge_proxy_type(type_str: str):
        if type_str == 'HTTPS':
            return ProxyTypeEnum.HTTPS.value
        if type_str == 'HTTP':
            return ProxyTypeEnum.HTTP.value
        else:
            return ProxyTypeEnum.UNKNOWN.value


@spider_register
class SpiderKuaiDaiLiIp(AbsSpider):
    """
    快代理IP 刷新速度: 极快
    https://www.kuaidaili.com/free
    """

    def __init__(self) -> None:
        super().__init__('快代理IP代理爬虫')

    def do_crawl(self, resp) -> List[ProxyEntity]:
        result = []
        soup = BeautifulSoup(resp, 'lxml')
        trs = soup.find('table').find('tbody').find_all('tr')
        for tr in trs:
            tds = tr.find_all('td')
            ip = tds[0].text
            port = tds[1].text
            proxy_cover = tds[2].text
            proxy_type = tds[3].text
            region = tds[4].text
            result.append(ProxyEntity(f'{proxy_type.lower()}://{ip}:{port}',
                                      # ip, port, protocol=proxy_type.lower(),
                                      source=self._name,
                                      proxy_type=self._judge_proxy_type(proxy_type),
                                      proxy_cover=self._judge_proxy_cover(proxy_cover),
                                      region=region))
        return result

    def get_urls(self) -> List[str]:
        return [
            'https://www.kuaidaili.com/free/inha',  # 高匿
            'https://www.kuaidaili.com/free/intr'  # 透明
        ]

    def get_page_range(self) -> Iterable:
        return range(1, 3)

    # 爬太快会被封
    def get_interval(self) -> int:
        return 3

    def _judge_proxy_type(self, type_str: str):
        type_low = type_str.lower()
        if type_low == 'http':
            return ProxyTypeEnum.HTTP.value
        elif type_low == 'https':
            return ProxyTypeEnum.HTTPS.value
        else:
            return ProxyTypeEnum.UNKNOWN.value

    def _judge_proxy_cover(self, cover_str: str):
        if cover_str == '透明':
            return ProxyCoverEnum.TRANSPARENT.value
        elif cover_str == '高匿名':
            return ProxyCoverEnum.HIGH_COVER.value
        else:
            return ProxyCoverEnum.UNKNOWN.value


@spider_register
class SpiderYunDaiLiIp(AbsSpider):
    """
    云代理IP 刷新速度: 快
    http://www.ip3366.net/free
    """

    def __init__(self) -> None:
        super().__init__('云代理IP爬虫')

    def do_crawl(self, resp) -> List[ProxyEntity]:
        result = []
        soup = BeautifulSoup(resp, 'lxml')
        trs = soup.find('table').find('tbody').find_all('tr')
        for tr in trs:
            tds = tr.find_all('td')
            ip = tds[0].text
            port = tds[1].text
            proxy_cover = tds[2].text
            proxy_type = tds[3].text
            region = tds[4].text
            result.append(ProxyEntity(f'{proxy_type.lower()}://{ip}:{port}',
                                      source=self._name,
                                      proxy_type=self._judge_proxy_type(proxy_type),
                                      proxy_cover=self._judge_proxy_cover(proxy_cover),
                                      region=region))
        return result

    def get_urls(self) -> List[str]:
        return [
            'http://www.ip3366.net/free/?stype=1',  # 高匿
            'http://www.ip3366.net/free/?stype=2'  # 透明 or 普匿
        ]

    def get_page_range(self) -> Iterable:
        return range(1, 3)

    def get_page_url(self, url, page) -> str:
        return f'{url}&page={page}'

    def _judge_proxy_type(self, type_str: str):
        type_low = type_str.lower()
        if type_low == 'http':
            return ProxyTypeEnum.HTTP.value
        elif type_low == 'https':
            return ProxyTypeEnum.HTTPS.value
        else:
            return ProxyTypeEnum.UNKNOWN.value

    def _judge_proxy_cover(self, cover_str: str):
        if cover_str == '透明代理IP':
            return ProxyCoverEnum.TRANSPARENT.value
        elif cover_str == '高匿代理IP':
            return ProxyCoverEnum.HIGH_COVER.value
        elif cover_str == '普通代理IP':
            return ProxyCoverEnum.NORMAL_COVER.value
        else:
            return ProxyCoverEnum.UNKNOWN.value


@spider_register
class SpiderIpHaiIp(AbsSpider):
    """
    IP海代理IP 刷新速度: 8分钟/1个
    有时会连不上
    http://www.iphai.com
    """

    def __init__(self) -> None:
        super().__init__('IP海代理IP爬虫')

    def do_crawl(self, resp) -> List[ProxyEntity]:
        result = []
        soup = BeautifulSoup(resp, 'lxml')
        table = soup.find('table')
        if table is None:
            return []
        tbody = soup.find('tbody')
        if tbody is None:
            return []
        trs = tbody.find_all('tr')
        for i, tr in enumerate(trs):
            if i == 0:
                continue
            tds = tr.find_all('td')
            ip = tds[0].text
            port = tds[1].text
            proxy_cover = tds[2].text
            proxy_type = tds[3].text if tds[3].text != '' else 'http'
            region = tds[4].text
            result.append(ProxyEntity(f'{proxy_type.lower()}://{ip}:{port}',
                                      source=self._name,
                                      proxy_type=self._judge_proxy_type(proxy_type),
                                      proxy_cover=self._judge_proxy_cover(proxy_cover),
                                      region=region))
        return result

    def get_urls(self) -> List[str]:
        return [
            'http://www.iphai.com/free/ng',  # 国内高匿
            'http://www.iphai.com/free/np',  # 国内普通
            'http://www.iphai.com/free/wg',  # 国外高匿
            'http://www.iphai.com/free/wp',  # 国外普通
        ]

    # 爬太快会被封
    def get_interval(self) -> int:
        return 2

    def get_page_url(self, url, page) -> str:
        return url

    @staticmethod
    def _judge_proxy_type(type_str: str):
        type_low = type_str.lower()
        if type_low == 'http':
            return ProxyTypeEnum.HTTP.value
        elif type_low == 'https':
            return ProxyTypeEnum.HTTPS.value
        else:
            return ProxyTypeEnum.UNKNOWN.value

    @staticmethod
    def _judge_proxy_cover(cover_str: str):
        if cover_str == '透明':
            return ProxyCoverEnum.TRANSPARENT.value
        elif cover_str == '高匿':
            return ProxyCoverEnum.HIGH_COVER.value
        elif cover_str == '普匿':
            return ProxyCoverEnum.NORMAL_COVER.value
        else:
            return ProxyCoverEnum.UNKNOWN.value


@spider_register
class SpiderMianFeiDaiLiIp(AbsSpider):
    """
    免费代理IP库
    http://ip.jiangxianli.com/
    """

    def __init__(self) -> None:
        super().__init__('免费代理IP爬虫')

    def do_crawl(self, resp) -> List[ProxyEntity]:
        result = []
        soup = BeautifulSoup(resp, 'lxml')
        table = soup.find('table')
        if table is None:
            return []
        tbody = soup.find('tbody')
        if tbody is None:
            return []
        trs = tbody.find_all('tr')
        for i, tr in enumerate(trs):
            if i == 0:
                continue
            tds = tr.find_all('td')
            logger.info('免费代理IP爬虫 -- ' + tds)
            ip = tds[0].text
            port = tds[1].text
            proxy_cover = tds[2].text
            proxy_type = tds[3].text if tds[2].text != '' else 'http'
            region = tds[4].text
            supplier = tds[5].text
            result.append(ProxyEntity(f'{proxy_type.lower()}://{ip}:{port}',
                                      source=self._name,
                                      supplier=supplier,
                                      proxy_type=self._judge_proxy_type(proxy_type),
                                      proxy_cover=self._judge_proxy_cover(proxy_cover),
                                      region=region))
        return result

    def get_interval(self) -> int:
        return 2

    def get_page_range(self) -> Iterable:
        return range(1, 4)

    def get_urls(self) -> List[str]:
        return ['http://ip.jiangxianli.com/?page={}']

    def get_page_url(self, url, page) -> str:
        return url.format(page)

    @staticmethod
    def _judge_proxy_type(type_str: str):
        type_low = type_str.lower()
        if type_low == 'http':
            return ProxyTypeEnum.HTTP.value
        elif type_low == 'https':
            return ProxyTypeEnum.HTTPS.value
        else:
            return ProxyTypeEnum.UNKNOWN.value

    @staticmethod
    def _judge_proxy_cover(cover_str: str):
        if cover_str == '透明':
            return ProxyCoverEnum.TRANSPARENT.value
        elif cover_str == '高匿':
            return ProxyCoverEnum.HIGH_COVER.value
        elif cover_str == '普匿':
            return ProxyCoverEnum.NORMAL_COVER.value
        else:
            return ProxyCoverEnum.UNKNOWN.value


if __name__ == '__main__':
    # proxies = []
    # tasks = [SpiderXiciIp().crawl()]
    # loop = asyncio.new_event_loop()
    # asyncio.set_event_loop(loop)
    # results = loop.run_until_complete(asyncio.gather(*tasks))
    # loop.close()
    results = asyncio.run(SpiderSpysOneIP().crawl())
    print(results)
