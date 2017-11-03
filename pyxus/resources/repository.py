from abc import abstractmethod
import re

from pyxus.resources.entity import Organization, Domain, Schema, Instance, Entity, SearchResult, SearchResultList


class Repository(object):

    def __init__(self, path, http_client):
        self.path = path
        self._http_client = http_client

    def create(self, entity):
        result = self._http_client.put(entity.path, entity.data)
        entity.data = result
        return entity

    def update(self, entity):
        path = "{}?rev={}".format(entity.path, entity.get_revision())
        result = self._http_client.put(path, entity.data)
        if result is not None:
            new_revision = result["rev"]
            entity.data = self._read(entity.id, new_revision)
        return entity

    def delete(self, entity, revision=None):
        if revision is None:
            revision = self._get_last_revision(entity.id)
        path = "{}?rev={}".format(entity.path, revision)
        result = self._http_client.delete(path)
        if result is not None:
            new_revision = result["rev"]
            entity.data = self._read(entity.id, new_revision)
        return entity

    def _read(self, identifier, revision=None):
        if revision is None:
            path = "{}/{}".format(self.path, identifier)
        else:
            path = "{}/{}?rev={}".format(self.path, identifier, revision)
        return self._http_client.get(path)

    def list(self, subpath=None, full_text_query=None, filter_query=None, from_index=None, size=None, deprecated=False):
        path = "{path}{subpath}/?{full_text_search_query}&{filter}&{from_index}&{size}&{deprecated}".format(
            path=self.path,
            subpath=subpath or '',
            full_text_search_query="q={}".format(full_text_query) if full_text_query is not None else '',
            filter="filter={}".format(filter_query) if filter_query is not None else '',
            from_index="from={}".format(from_index) if from_index is not None else '',
            size="size={}".format(size) if size is not None else '',
            deprecated="deprecated={}".format(deprecated) if deprecated is not None else ''
        )
        result = self._http_client.get(path)
        if result is not None:
            results = [SearchResult(r) for r in result["results"]]
            return SearchResultList(result["total"], results)
        return None

    def _get_last_revision(self, identifier):
        current_revision = self._read(identifier)
        return current_revision.get("rev") or 0

    def resolve_all(self, search_result_list):
        return [self.resolve(search_result) for search_result in search_result_list.results]

    @abstractmethod
    def resolve(self, search_result):
        pass


class OrganizationRepository(Repository):

    def __init__(self, http_client):
        super(OrganizationRepository, self).__init__(Organization.path, http_client)

    def read(self, name, revision=None):
        data = self._read(name, revision)
        return Organization(name, data, self.path) if data is not None else None

    def resolve(self, search_result):
        identifier = Entity.extract_id_from_url(search_result.self_link, self.path)
        data = self._read(identifier)
        return Organization(identifier, data, self.path) if data is not None else None


class DomainRepository(Repository):

    def __init__(self, http_client):
        super(DomainRepository, self).__init__(Domain.path, http_client)

    def read(self, organization, domain, revision=None):
        identifier = Domain.create_id(organization, domain)
        data = self._read(identifier, revision)
        return Domain(identifier, data, self.path) if data is not None else None

    def resolve(self, search_result):
        identifier = Entity.extract_id_from_url(search_result.self_link, self.path)
        data = self._read(identifier)
        return Domain(identifier, data, self.path) if data is not None else None


class SchemaRepository(Repository):

    def __init__(self, http_client):
        super(SchemaRepository, self).__init__(Schema.path, http_client)

    def read(self, organization, domain, schema, version, revision=None):
        identifier = Schema.create_id(organization, domain, schema, version)
        data = self._read(identifier, revision)
        return Schema(identifier, data, self.path) if data is not None else None

    def publish(self, entity, publish, revision=None):
        if revision is None:
            revision = self._get_last_revision(entity.id)
        path = "{}/config?rev={}".format(entity.path, revision)
        result = self._http_client.patch(path, {
            'published': publish
        })
        if result is not None:
            new_revision = result["rev"]
            entity.data = self._read(entity.id, new_revision)
        return entity

    def resolve(self, search_result):
        identifier = Entity.extract_id_from_url(search_result.self_link, self.path)
        data = self._read(identifier)
        return Schema(identifier, data, self.path) if data is not None else None


class InstanceRepository(Repository):

    def __init__(self, http_client):
        super(InstanceRepository, self).__init__(Instance.path, http_client)

    def create(self, entity):
        result = self._http_client.post(entity.path, entity.data)
        entity.data = result
        entity.id = Instance.extract_id_from_url(result.get("@id"), self.path)
        entity.build_path()
        return entity

    @staticmethod
    def _extract_uuid(full_id_string):
        regex = "[^/]*$"
        r = re.search(regex, full_id_string)
        if r is not None:
            return r.group(0)
        return None

    def read_by_full_id(self, full_id, revision=None):
        data = self._read(full_id, revision)
        return Instance(full_id, data, self.path) if data is not None else None

    def read(self, organization, domain, schema, version, uuid, revision=None):
        identifier = Instance.create_id(organization, domain, schema, version)+"/"+uuid
        data = self._read(identifier, revision)
        return Instance(identifier, data, self.path) if data is not None else None

    def resolve(self, search_result):
        identifier = Entity.extract_id_from_url(search_result.self_link, self.path)
        data = self._read(identifier)
        return Instance(identifier, data, self.path) if data is not None else None