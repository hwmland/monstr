import NodesPanel from "../components/NodesPanel";
import ReputationsPanel from "../components/ReputationsPanel";
import usePanelVisibilityStore from "../store/usePanelVisibility";

const HomePage = () => {
  const { isVisible } = usePanelVisibilityStore();
  return (
    <div className="page">
      <NodesPanel />
      {isVisible("reputations") ? <ReputationsPanel /> : null}
    </div>
  );
};

export default HomePage;
