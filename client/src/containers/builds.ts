import * as _ from 'lodash';
import { connect } from 'react-redux';
import { Dispatch } from 'redux';

import Builds from '../components/builds';
import { AppState } from '../constants/types';
import { isTrue } from '../constants/utils';
import { BuildModel } from '../models/build';

import * as actions from '../actions/build';
import * as search_actions from '../actions/search';
import { SearchModel } from '../models/search';

interface OwnProps {
  user: string;
  projectName?: string;
  bookmarks?: boolean;
  useFilters?: boolean;
  showBookmarks?: boolean;
  fetchData?: () => any;
}

export function mapStateToProps(state: AppState, ownProps: OwnProps) {
  // let useFilter = () => {
  //   let builds: BuildModel[] = [];
  //   let project = state.projects.byUniqueNames[ownProps.projectName];
  //   let BuildNames = project.builds;
  //   BuildNames.forEach(
  //     function (build: string, idx: number) {
  //       builds.push(state.builds.byUniqueNames[build]);
  //     });
  //   return {builds: builds, count: project.num_builds};
  // };

  const useLastFetched = () => {
    const buildNames = state.builds.lastFetched.names;
    const count = state.builds.lastFetched.count;
    const builds: BuildModel[] = [];
    buildNames.forEach(
      (build: string, idx: number) => {
        builds.push(state.builds.byUniqueNames[build]);
      });
    return {builds, count};
  };
  const results = useLastFetched();

  return {
    isCurrentUser: state.auth.user === ownProps.user,
    builds: results.builds,
    count: results.count,
    useFilters: isTrue(ownProps.useFilters),
    showBookmarks: isTrue(ownProps.showBookmarks),
    bookmarks: isTrue(ownProps.bookmarks),
  };
}

export interface DispatchProps {
  onCreate?: (build: BuildModel) => actions.BuildAction;
  onDelete: (buildName: string) => actions.BuildAction;
  onStop: (buildName: string) => actions.BuildAction;
  onUpdate?: (build: BuildModel) => actions.BuildAction;
  bookmark?: (buildName: string) => actions.BuildAction;
  unbookmark?: (buildName: string) => actions.BuildAction;
  fetchData?: (offset?: number, query?: string, sort?: string) => actions.BuildAction;
  fetchSearches?: () => search_actions.SearchAction;
  createSearch?: (data: SearchModel) => search_actions.SearchAction;
  deleteSearch?: (searchId: number) => search_actions.SearchAction;
}

export function mapDispatchToProps(dispatch: Dispatch<actions.BuildAction>, ownProps: OwnProps): DispatchProps {
  return {
    onCreate: (build: BuildModel) => dispatch(actions.createBuildActionCreator(build)),
    onDelete: (buildName: string) => dispatch(actions.deleteBuild(buildName)),
    onStop: (buildName: string) => dispatch(actions.stopBuild(buildName)),
    bookmark: (buildName: string) => dispatch(actions.bookmark(buildName)),
    unbookmark: (buildName: string) => dispatch(actions.unbookmark(buildName)),
    onUpdate: (build: BuildModel) => dispatch(actions.updateBuildActionCreator(build)),
    fetchSearches: () => {
      if (ownProps.projectName) {
        return dispatch(search_actions.fetchBuildSearches(ownProps.projectName));
      } else {
        throw new Error('Builds container does not have project.');
      }
    },
    createSearch: (data: SearchModel) => {
      if (ownProps.projectName) {
        return dispatch(search_actions.createBuildSearch(ownProps.projectName, data));
      } else {
        throw new Error('Builds container does not have project.');
      }
    },
    deleteSearch: (searchId: number) => {
      if (ownProps.projectName) {
        return dispatch(search_actions.deleteBuildSearch(ownProps.projectName, searchId));
      } else {
        throw new Error('Builds container does not have project.');
      }
    },
    fetchData: (offset?: number, query?: string, sort?: string) => {
      const filters: {[key: string]: number|boolean|string} = {};
      if (query) {
        filters.query = query;
      }
      if (sort) {
        filters.sort = sort;
      }
      if (offset) {
        filters.offset = offset;
      }
      if (_.isNil(ownProps.projectName) && ownProps.bookmarks) {
        return dispatch(actions.fetchBookmarkedBuilds(ownProps.user, filters));
      } else if (ownProps.projectName) {
        return dispatch(actions.fetchBuilds(ownProps.projectName, filters));
      } else {
        throw new Error('Builds container expects either a project name or bookmarks.');
      }
    }
  };
}

export default connect(mapStateToProps, mapDispatchToProps)(Builds);
