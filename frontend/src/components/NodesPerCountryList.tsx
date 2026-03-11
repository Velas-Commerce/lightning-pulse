import { useState, useEffect } from "react";
import type { NodesPerCountry } from "../types";
import { fetchNodesPerCountry } from "../api";

function NodesPerCountryList() {
  const [nodes_per_country, setNodesPerCountry] = useState<NodesPerCountry[] | null>(null);

  useEffect(() => {
    fetchNodesPerCountry().then((data) => setNodesPerCountry(data));
  }, []);

  return (
    <div>
      {nodes_per_country && (
        <ul>
          {nodes_per_country.map((country) => (
            <li key={country.iso}>
              {country.iso}: {country.count} nodes
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default NodesPerCountryList;
